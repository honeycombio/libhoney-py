'''Tests for libhoney/transmission.py'''

import transmission

import mock
import unittest
import requests_mock
import datetime
from six.moves import queue


class FakeThread():
    def start(self):
        return


class TestTransmissionInit(unittest.TestCase):
    def test_defaults(self):
        ft = FakeThread()
        transmission.threading.Thread = mock.Mock(return_value=ft)
        t = transmission.Transmission()
        self.assertEqual(t.max_concurrent_batches, 10)
        self.assertIsInstance(t.pending, queue.Queue)
        self.assertIsInstance(t.responses, queue.Queue)
        self.assertEqual(t.block_on_send, False)
        self.assertEqual(t.block_on_response, False)
        self.assertEqual(len(t.threads), 10)

    def test_args(self):
        ft = FakeThread()
        transmission.threading.Thread = mock.Mock(return_value=ft)
        t = transmission.Transmission(max_concurrent_batches=4, block_on_send=True, block_on_response=True)
        self.assertEqual(t.max_concurrent_batches, 4)
        self.assertEqual(t.block_on_send, True)
        self.assertEqual(t.block_on_response, True)
        self.assertEqual(len(t.threads), 4)


class FakeEvent():
    def __init__(self):
        self.created_at = datetime.datetime.now()


class TestTransmissionSend(unittest.TestCase):
    def test_send(self):
        transmission.sd = mock.Mock()
        ft = FakeThread()
        transmission.threading.Thread = mock.Mock(return_value=ft)
        t = transmission.Transmission()
        qsize = 4
        t.pending.qsize = mock.Mock(return_value=qsize)
        t.pending.put = mock.Mock()
        t.pending.put_nowait = mock.Mock()
        t.responses.put = mock.Mock()
        t.responses.put_nowait = mock.Mock()
        # put an event non-blocking
        ev = FakeEvent()
        ev.metadata = None
        t.send(ev)
        transmission.sd.gauge.assert_called_with("queue_length", 4)
        t.pending.put_nowait.assert_called_with(ev)
        t.pending.put.assert_not_called()
        transmission.sd.incr.assert_called_with("messages_queued")
        t.pending.put.reset_mock()
        t.pending.put_nowait.reset_mock()
        transmission.sd.reset_mock()
        # put an event blocking
        t.block_on_send = True
        t.send(ev)
        t.pending.put.assert_called_with(ev)
        t.pending.put_nowait.assert_not_called()
        transmission.sd.incr.assert_called_with("messages_queued")
        transmission.sd.reset_mock()
        # put an event non-blocking queue full
        t.block_on_send = False
        t.pending.put_nowait = mock.Mock(side_effect=queue.Full())
        t.send(ev)
        transmission.sd.incr.assert_called_with("queue_overflow")
        t.responses.put_nowait.assert_called_with({
            "status_code": 0, "duration": 0,
            "metadata": None, "body": "",
            "error": "event dropped; queue overflow",
        })


class TestTransmissionPrivateSend(unittest.TestCase):
    def test_send(self):
        transmission.sd = mock.Mock()
        ft = FakeThread()
        transmission.threading.Thread = mock.Mock(return_value=ft)
        t = transmission.Transmission()
        t.responses.put_nowait = mock.Mock()
        t.responses.put = mock.Mock()
        fakeNow = datetime.datetime(2012, 1, 1, 10, 10, 10)
        transmission.get_now = mock.MagicMock(return_value=fakeNow)

        with requests_mock.Mocker() as m:
            ev = FakeEvent()
            ev.writekey = "writeme"
            ev.dataset = "datame"
            ev.api_host = "http://urlme/"
            ev.metadata = "metame"
            ev.sample_rate = 3
            ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
            m.post("http://urlme/1/events/datame",
                text="", status_code=200,
                request_headers={
                    "X-Event-Time": "2013-01-01T11:11:11Z",
                    "X-Honeycomb-Team": "writeme",
                })
            t._send(ev)
            transmission.sd.incr.assert_called_with("messages_sent")
            expected_response = {
                "status_code": 200,
                "duration": 0,
                "metadata": ev.metadata,
                "body": "",
                "error": "",
            }
            t.responses.put_nowait.assert_called_with(expected_response)

            # and with subsecond precision, now
            ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11, 12345)
            m.post("http://urlme/1/events/datame",
                text="", status_code=200,
                request_headers={
                    "X-Event-Time": "2013-01-01T11:11:11.012345Z",
                    "X-Honeycomb-Team": "writeme",
                })
            t._send(ev)
