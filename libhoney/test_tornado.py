'''Tests for libhoney/transmission.py'''
import datetime
import json
import unittest
from unittest import mock

import tornado

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
            future = tornado.concurrent.Future()
            future.set_result("OK")
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

                # wait on the batch to be "sent"
                # we can detect this when data has been inserted into the
                # batch data dictionary
                start_time = datetime.datetime.now()
                while not t.batch_data:
                    if datetime.datetime.now() - start_time > datetime.timedelta(0, 10):
                        self.fail("timed out waiting on batch send")
                    yield tornado.gen.sleep(0.01)
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


class TestTornadoTransmissionUnencodableEvents(unittest.TestCase):
    def test_bad_event_is_reported_and_the_rest_is_sent(self):
        with mock.patch('libhoney.transmission.AsyncHTTPClient.fetch') as fetch_mock,\
                mock.patch('statsd.StatsClient') as m_statsd:
            future = tornado.concurrent.Future()
            future.set_result("OK")
            fetch_mock.return_value = future
            m_statsd.return_value = mock.Mock()

            loop = {}
            loop["self"] = loop

            def make_event(fields, metadata):
                ev = mock.Mock(metadata=metadata, writekey="abc123",
                               dataset="blargh", api_host="https://example.com",
                               sample_rate=1, created_at=datetime.datetime.now())
                ev.fields.return_value = fields
                return ev

            @tornado.gen.coroutine
            def _test():
                t = transmission.TornadoTransmission()
                t.start()
                t.send(make_event({"n": 1}, "good"))
                t.send(make_event({"loop": loop}, "bad"))
                try:
                    resp = yield t.responses.get(datetime.timedelta(0, 10))
                    self.assertEqual(resp["metadata"], "bad")
                    self.assertEqual(resp["status_code"], 0)
                except tornado.util.TimeoutError:
                    self.fail("timed out waiting on response queue")
                finally:
                    t.close()

            tornado.ioloop.IOLoop.current().run_sync(_test)
            self.assertEqual(fetch_mock.call_count, 1)
            req = fetch_mock.call_args[0][0]
            self.assertEqual([e["data"] for e in json.loads(req.body)], [{"n": 1}])


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
