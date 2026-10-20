'''Tests for libhoney/transmission.py'''
import datetime
import io
import unittest
from unittest import mock

import tornado
import tornado.testing
import tornado.web

import libhoney
from libhoney import transmission
from platform import python_version


class TestTornadoTransmissionInit(unittest.TestCase):
    def test_defaults(self):
        t = transmission.TornadoTransmission()
        self.assertIsInstance(t.batch_sem, tornado.locks.Semaphore)
        self.assertIsInstance(t.pending, tornado.queues.Queue)
        self.assertIsInstance(t.responses, tornado.queues.Queue)
        self.assertEqual(t.block_on_send, False)
        self.assertEqual(t.block_on_response, False)
        self.assertEqual(transmission.has_tornado, True)

    def test_args(self):
        t = transmission.TornadoTransmission(
            max_concurrent_batches=4, block_on_send=True, block_on_response=True)
        t.start()
        self.assertEqual(t.block_on_send, True)
        self.assertEqual(t.block_on_response, True)
        t.close()

    def test_user_agent_addition(self):
        ''' ensure user_agent_addition is included in the User-Agent header '''
        with mock.patch('libhoney.transmission.AsyncHTTPClient') as m_client:
            transmission.TornadoTransmission(user_agent_addition='foo/1.0')
            expected = f"libhoney-py/{libhoney.version.VERSION} (tornado/{tornado.version}) foo/1.0 python/{python_version()}"
            m_client.assert_called_once_with(
                force_instance=True,
                defaults=dict(user_agent=expected),
            )


class TestTornadoTransmissionSend(unittest.TestCase):
    def test_send(self):
        with mock.patch('libhoney.transmission.AsyncHTTPClient.fetch') as fetch_mock,\
                mock.patch('statsd.StatsClient') as m_statsd:
            def fetch(request, **_kwargs):
                future = tornado.concurrent.Future()
                future.set_result(tornado.httpclient.HTTPResponse(
                    request, 200, buffer=io.BytesIO(b'[{"status": 202}]')))
                return future

            fetch_mock.side_effect = fetch
            m_statsd.return_value = mock.Mock()

            @tornado.gen.coroutine
            def _test():
                t = transmission.TornadoTransmission()
                t.start()

                ev = mock.Mock(metadata=None, writekey="abc123",
                               dataset="blargh", api_host="https://example.com",
                               sample_rate=1, created_at=datetime.datetime.now())
                ev.fields.return_value = {"foo": "bar"}
                t.send(ev)

                try:
                    response = yield t.responses.get(datetime.timedelta(seconds=1))
                    self.assertEqual(response["status_code"], 202)
                    self.assertIsNone(response["error"])
                    self.assertEqual(t.batch_data, {})
                finally:
                    t.close()

            tornado.ioloop.IOLoop.current().run_sync(_test)
            m_statsd.return_value.incr.assert_any_call("messages_queued")
            self.assertTrue(fetch_mock.called)


class TestTornadoTransmissionSendError(unittest.TestCase):
    def test_send(self):
        with mock.patch('libhoney.transmission.AsyncHTTPClient.fetch') as fetch_mock,\
                mock.patch('statsd.StatsClient') as m_statsd:
            future = tornado.concurrent.Future()
            ex = Exception("oh poo!")
            future.set_exception(ex)
            fetch_mock.return_value = future
            m_statsd.return_value = mock.Mock()

            @tornado.gen.coroutine
            def _test():
                t = transmission.TornadoTransmission()
                t.start()

                ev = mock.Mock(metadata=None, writekey="abc123",
                               dataset="blargh", api_host="https://example.com",
                               sample_rate=1, created_at=datetime.datetime.now())
                ev.fields.return_value = {"foo": "bar"}
                t.send(ev)

                try:
                    resp = yield t.responses.get(datetime.timedelta(0, 10))
                    self.assertEqual(resp["error"], ex)
                except tornado.util.TimeoutError:
                    self.fail("timed out waiting on response queue")
                finally:
                    t.close()

            tornado.ioloop.IOLoop.current().run_sync(_test)


class TestTornadoTransmissionQueueOverflow(unittest.TestCase):
    def test_send(self):
        with mock.patch('statsd.StatsClient') as m_statsd:
            m_statsd.return_value = mock.Mock()

            t = transmission.TornadoTransmission()
            t.pending = tornado.queues.Queue(maxsize=2)
            t.responses = tornado.queues.Queue(maxsize=1)
            # we don't call start on transmission here, which will cause
            # the queue to pile up

            t.send(mock.Mock())
            t.send(mock.Mock())
            t.send(mock.Mock())  # should overflow sending and land on response
            m_statsd.return_value.incr.assert_any_call("queue_overflow")
            # shouldn't throw exception when response is full
            t.send(mock.Mock())


class TestTornadoResponsesOverHTTP(tornado.testing.AsyncHTTPTestCase):
    """Exercise public event sends with the real Tornado HTTP transport."""

    def get_app(self):
        owner = self

        class BatchHandler(tornado.web.RequestHandler):
            def post(self, _dataset):
                owner.received.append(self.request.body)
                self.set_status(owner.http_status)
                self.finish(owner.response_body)

        self.received = []
        self.http_status = 200
        self.response_body = '[{"status": 202}]'
        return tornado.web.Application([(r"/1/batch/(.*)", BatchHandler)])

    async def send_event(self):
        xmit = transmission.TornadoTransmission(
            send_frequency=datetime.timedelta(milliseconds=1))
        client = libhoney.client.Client(
            writekey="dummy-key", dataset="test", api_host=self.get_url('/'),
            transmission_impl=xmit)
        event = client.new_event()
        event.add_field("test", True)
        event.metadata = {"event": "one"}
        try:
            event.send()
            response = await xmit.responses.get(datetime.timedelta(seconds=1))
            self.assertEqual(response["metadata"], {"event": "one"})
            self.assertEqual(len(self.received), 1)
            self.assertEqual(xmit.batch_data, {})
            return response
        finally:
            client.close()
            await tornado.gen.sleep(0)
            xmit.http_client.close()

    @tornado.testing.gen_test
    async def test_success_is_reported_and_batch_state_is_released(self):
        response = await self.send_event()
        self.assertEqual(response["status_code"], 202)
        self.assertIsNone(response["error"])

    @tornado.testing.gen_test
    async def test_http_error_retains_the_actual_status(self):
        self.http_status = 400
        self.response_body = '{"error": "invalid test request"}'
        response = await self.send_event()
        self.assertEqual(response["status_code"], 400)
        self.assertIsInstance(response["error"], tornado.httpclient.HTTPClientError)

    @tornado.testing.gen_test
    async def test_invalid_json_is_reported_and_batch_state_is_released(self):
        self.response_body = 'not json'
        response = await self.send_event()
        self.assertEqual(response["status_code"], 200)
        self.assertIsInstance(response["error"], ValueError)
