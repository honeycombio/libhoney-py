'''Tests for libhoney/transmission.py'''

import datetime
import unittest

import mock
import six
import tornado
import libhoney
import transmission

PATCH_NAMESPACE='transmission'
if six.PY2:
    PATCH_NAMESPACE='libhoney.transmission'


class TestTornadoTransmissionInit(unittest.TestCase):
    def test_defaults(self):
        t = transmission.TornadoTransmission()
        self.assertIsInstance(t.batch_sem, tornado.locks.Semaphore)
        self.assertIsInstance(t.pending, tornado.queues.Queue)
        self.assertIsInstance(t.responses, tornado.queues.Queue)
        self.assertEqual(t.block_on_send, False)
        self.assertEqual(t.block_on_response, False)

    def test_args(self):
        t = transmission.TornadoTransmission(max_concurrent_batches=4, block_on_send=True, block_on_response=True)
        t.start()
        self.assertEqual(t.block_on_send, True)
        self.assertEqual(t.block_on_response, True)
        t.close()

    def test_user_agent_addition(self):
        ''' ensure user_agent_addition is included in the User-Agent header '''
        with mock.patch(PATCH_NAMESPACE + '.AsyncHTTPClient') as m_client:
            transmission.TornadoTransmission(user_agent_addition='foo/1.0')
            expected = "libhoney-py/" + libhoney.version.VERSION + " foo/1.0"
            m_client.assert_called_once_with(
                force_instance=True,
                defaults=dict(user_agent=expected),
            )


class TestTornadoTransmissionSend(unittest.TestCase):
    def test_send(self):
        with mock.patch(PATCH_NAMESPACE+'.AsyncHTTPClient') as m_http,\
                mock.patch('statsd.StatsClient') as m_statsd:
            m_http.return_value = mock.Mock()
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
                while not t.batch_data:
                    yield tornado.gen.sleep(0.01)
                t.close()

            tornado.ioloop.IOLoop.current().run_sync(_test)
            m_statsd.return_value.incr.assert_any_call("messages_queued")
            self.assertTrue(m_http.return_value.fetch.called)


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
            t.send(mock.Mock()) # should overflow sending and land on response
            m_statsd.return_value.incr.assert_any_call("queue_overflow")
            t.send(mock.Mock()) # shouldn't throw exception when response is full
