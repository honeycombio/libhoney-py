'''Tests for libhoney/transmission.py'''

import libhoney
from libhoney import transmission
from libhoney.version import VERSION
from platform import python_version

import datetime
import gzip
import httpretty
import io
import json
from unittest import mock
import requests_mock
import time
import unittest
import queue


class TestTransmissionInit(unittest.TestCase):
    def test_defaults(self):
        t = transmission.Transmission()
        self.assertEqual(t.max_concurrent_batches, 10)
        self.assertIsInstance(t.pending, queue.Queue)
        self.assertEqual(t.pending.maxsize, 1000)
        self.assertIsInstance(t.responses, queue.Queue)
        self.assertEqual(t.responses.maxsize, 2000)
        self.assertEqual(t.block_on_send, False)
        self.assertEqual(t.block_on_response, False)

    def test_args(self):
        t = transmission.Transmission(
            max_concurrent_batches=4, block_on_send=True, block_on_response=True)
        t.start()
        self.assertEqual(t.max_concurrent_batches, 4)
        self.assertEqual(t.block_on_send, True)
        self.assertEqual(t.block_on_response, True)
        t.close()

    def test_user_agent_addition(self):
        ''' ensure user_agent_addition is included in the User-Agent header '''
        with mock.patch('libhoney.transmission.Transmission._get_requests_session') as m_session:
            transmission.Transmission(gzip_enabled=False)
            expected = "libhoney-py/" + libhoney.version.VERSION + " python/" + python_version()
            m_session.return_value.headers.update.assert_called_once_with({
                'User-Agent': expected
            })
        with mock.patch('libhoney.transmission.Transmission._get_requests_session') as m_session:
            transmission.Transmission(
                user_agent_addition='foo/1.0', gzip_enabled=False)
            expected = "libhoney-py/" + libhoney.version.VERSION + " foo/1.0" + " python/" + python_version()
            m_session.return_value.headers.update.assert_called_once_with({
                'User-Agent': expected
            })


class FakeEvent():
    def __init__(self):
        self.created_at = datetime.datetime.now()
        self.metadata = {}


class TestTransmissionSend(unittest.TestCase):
    def test_send(self):
        t = transmission.Transmission()
        t.sd = mock.Mock()
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
        t.sd.gauge.assert_called_with("queue_length", 4)
        t.pending.put_nowait.assert_called_with(ev)
        t.pending.put.assert_not_called()
        t.sd.incr.assert_called_with("messages_queued")
        t.pending.put.reset_mock()
        t.pending.put_nowait.reset_mock()
        t.sd.reset_mock()
        # put an event blocking
        t.block_on_send = True
        t.send(ev)
        t.pending.put.assert_called_with(ev)
        t.pending.put_nowait.assert_not_called()
        t.sd.incr.assert_called_with("messages_queued")
        t.sd.reset_mock()
        # put an event non-blocking queue full
        t.block_on_send = False
        t.pending.put_nowait = mock.Mock(side_effect=queue.Full())
        t.send(ev)
        t.sd.incr.assert_called_with("queue_overflow")
        t.responses.put_nowait.assert_called_with({
            "status_code": 0, "duration": 0,
            "metadata": None, "body": "",
            "error": "event dropped; queue overflow",
        })

    @httpretty.activate
    def test_send_batch_will_retry_once(self):
        libhoney.init()
        # create two responses to the batch event post
        # first timeout, then accept the batch
        httpretty.register_uri(
            httpretty.POST,
            "http://urlme/1/batch/datame",
            responses=[
                httpretty.Response(
                    body='{"message": "Timeout"}',
                    status=500,
                ),
                httpretty.Response(
                    body=json.dumps([{"status": 202}]),
                    status=200,
                ),
            ]
        )

        t = transmission.Transmission()
        t.start()
        ev = libhoney.Event()
        ev.writekey = "writeme"
        ev.dataset = "datame"
        ev.api_host = "http://urlme/"
        ev.metadata = "metadaaata"
        ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
        t.send(ev)
        t.close()

        resp_count = 0
        while not t.responses.empty():
            resp = t.responses.get()
            if resp is None:
                break
            # verify the batch was accepted
            assert resp["status_code"] == 202
            assert resp["metadata"] == "metadaaata"
            resp_count += 1

    def test_send_gzip(self):
        libhoney.init()
        with requests_mock.Mocker() as m:
            m.post("http://urlme/1/batch/datame",
                   text=json.dumps([{"status": 202}]), status_code=200,
                   request_headers={"X-Honeycomb-Team": "writeme"})

            t = transmission.Transmission(block_on_send=True)
            t.start()
            ev = libhoney.Event()
            ev.writekey = "writeme"
            ev.dataset = "datame"
            ev.api_host = "http://urlme/"
            ev.metadata = "metadaaata"
            ev.sample_rate = 3
            ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
            ev.add_field("key", "asdf")
            t.send(ev)

            # sending is async even with the mock so block until it happens
            resp_received = False
            while not resp_received:
                resp = t.responses.get()
                if resp is None:
                    break

                self.assertEqual(resp["status_code"], 202)
                self.assertEqual(resp["metadata"], "metadaaata")
                resp_received = True

            for req in m.request_history:
                # verify gzip payload is sane by decompressing and checking contents
                self.assertEqual(
                    req.headers['Content-Encoding'], 'gzip', "content encoding should be gzip")
                gz = gzip.GzipFile(fileobj=io.BytesIO(req.body), mode='rb')
                # json.load in python 3.5 doesn't like binary files, so we can't pass
                # the gzip stream directly to it
                uncompressed = gz.read().decode()
                data = json.loads(uncompressed)
                self.assertEqual(data[0]['samplerate'], 3)
                self.assertEqual(data[0]['data']['key'], 'asdf')


class TestTransmissionUnencodableEvents(unittest.TestCase):
    '''One event that cannot be turned into JSON must not cost the rest of
    its batch.'''

    def _event(self, fields, metadata=None):
        ev = FakeEvent()
        ev.metadata = metadata
        ev.writekey = "writeme"
        ev.dataset = "datame"
        ev.api_host = "http://urlme/"
        ev.sample_rate = 1
        ev.fields = lambda: fields
        return ev

    def _send_all(self, events, **kwargs):
        with requests_mock.Mocker() as m:
            m.post("http://urlme/1/batch/datame",
                   text=json.dumps(len(events) * [{"status": 202}]),
                   status_code=200)
            t = transmission.Transmission(gzip_enabled=False, **kwargs)
            t.start()
            for ev in events:
                t.send(ev)
            t.close()
            responses = []
            while not t.responses.empty():
                resp = t.responses.get()
                if resp is not None:
                    responses.append(resp)
            return m.request_history, responses

    def test_circular_reference_only_fails_that_event(self):
        loop = {}
        loop["self"] = loop
        events = [
            self._event({"n": 1}, metadata="good-1"),
            self._event({"loop": loop}, metadata="bad"),
            self._event({"n": 2}, metadata="good-2"),
        ]
        requests, responses = self._send_all(events)

        sent = [e["data"] for r in requests for e in r.json()]
        self.assertEqual(sent, [{"n": 1}, {"n": 2}])
        by_meta = {r["metadata"]: r for r in responses}
        self.assertEqual(by_meta["good-1"]["status_code"], 202)
        self.assertEqual(by_meta["good-2"]["status_code"], 202)
        self.assertEqual(by_meta["bad"]["status_code"], 0)
        self.assertIsNotNone(by_meta["bad"]["error"])

    def test_batch_of_only_unencodable_events_makes_no_request(self):
        loop = []
        loop.append(loop)
        requests, responses = self._send_all(
            [self._event({"loop": loop}, metadata="bad")])

        self.assertEqual(requests, [])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["metadata"], "bad")
        self.assertIsNotNone(responses[0]["error"])

    def test_nan_and_infinity_are_sent_as_strings(self):
        events = [self._event({
            "nan": float("nan"),
            "inf": float("inf"),
            "ninf": float("-inf"),
            "nested": {"values": [1.5, float("nan")]},
            "ok": 2.5,
        })]
        requests, responses = self._send_all(events)

        def refuse(name):
            raise ValueError("bare " + name + " in request body")
        # parse_constant only fires for a bare NaN, Infinity or -Infinity
        json.loads(requests[0].text, parse_constant=refuse)
        data = requests[0].json()[0]["data"]
        self.assertEqual(data["nan"], "NaN")
        self.assertEqual(data["inf"], "Infinity")
        self.assertEqual(data["ninf"], "-Infinity")
        self.assertEqual(data["nested"], {"values": [1.5, "NaN"]})
        self.assertEqual(data["ok"], 2.5)
        self.assertEqual(responses[0]["status_code"], 202)

    def test_non_string_keys_are_converted(self):
        events = [self._event({"tags": {("a", 1): "x", 7: "y"}})]
        requests, responses = self._send_all(events)

        data = requests[0].json()[0]["data"]
        self.assertEqual(data["tags"], {"('a', 1)": "x", "7": "y"})
        self.assertEqual(responses[0]["status_code"], 202)


class TestEncodeBatch(unittest.TestCase):
    def test_body_is_strict_json(self):
        ev = FakeEvent()
        ev.sample_rate = 1
        ev.fields = lambda: {"v": float("nan")}
        body, sendable, failures = transmission.encode_batch([ev])

        def refuse(name):
            raise ValueError("non-finite constant " + name)
        # parse_constant is only called for bare NaN, Infinity, -Infinity
        parsed = json.loads(body, parse_constant=refuse)
        self.assertEqual(parsed[0]["data"], {"v": "NaN"})
        self.assertEqual(sendable, [ev])
        self.assertEqual(failures, [])

    def test_empty(self):
        self.assertEqual(transmission.encode_batch([]), ("[]", [], []))


class TestTransmissionQueueOverflow(unittest.TestCase):
    def test_send(self):
        t = transmission.Transmission(max_pending=2, max_responses=1)

        t.send(FakeEvent())
        t.send(FakeEvent())
        t.send(FakeEvent())  # should overflow sending and land on response
        t.send(FakeEvent())  # shouldn't throw exception when response is full


class TestTransmissionPrivateSend(unittest.TestCase):
    def setUp(self):
        # reset global state with each test
        libhoney.close()

    def test_batching(self):
        libhoney.init()
        with requests_mock.Mocker() as m:
            m.post("http://urlme/1/batch/datame",
                   text=json.dumps(200 * [{"status": 202}]), status_code=200,
                   request_headers={"X-Honeycomb-Team": "writeme"})

            t = transmission.Transmission(gzip_enabled=False)
            t.start()
            for i in range(300):
                ev = libhoney.Event()
                ev.writekey = "writeme"
                ev.dataset = "datame"
                ev.api_host = "http://urlme/"
                ev.metadata = "metadaaata"
                ev.sample_rate = 3
                ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
                ev.add_field("key", i)
                t.send(ev)
            t.close()

            resp_count = 0
            while not t.responses.empty():
                resp = t.responses.get()
                if resp is None:
                    break
                assert resp["status_code"] == 202
                assert resp["metadata"] == "metadaaata"
                resp_count += 1
            assert resp_count == 300

            for req in m.request_history:
                body = req.json()
                for event in body:
                    assert event["time"] == "2013-01-01T11:11:11Z"
                    assert event["samplerate"] == 3

    def test_grouping(self):
        libhoney.init()
        with requests_mock.Mocker() as m:
            m.post("http://urlme/1/batch/dataset",
                   text=json.dumps(100 * [{"status": 202}]), status_code=200,
                   request_headers={"X-Honeycomb-Team": "writeme"})

            m.post("http://urlme/1/batch/alt_dataset",
                   text=json.dumps(100 * [{"status": 202}]), status_code=200,
                   request_headers={"X-Honeycomb-Team": "writeme"})

            t = transmission.Transmission(
                max_concurrent_batches=1, gzip_enabled=False)
            t.start()

            builder = libhoney.Builder()
            builder.writekey = "writeme"
            builder.dataset = "dataset"
            builder.api_host = "http://urlme/"
            for i in range(100):
                ev = builder.new_event()
                ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
                ev.add_field("key", i)
                t.send(ev)

            builder.dataset = "alt_dataset"
            for i in range(100):
                ev = builder.new_event()
                ev.created_at = datetime.datetime(2013, 1, 1, 11, 11, 11)
                ev.add_field("key", i)
                t.send(ev)

            t.close()
            resp_count = 0
            while not t.responses.empty():
                resp = t.responses.get()
                if resp is None:
                    break
                assert resp["status_code"] == 202
                resp_count += 1
            assert resp_count == 200

            assert ({h.url for h in m.request_history} ==
                    {"http://urlme/1/batch/dataset", "http://urlme/1/batch/alt_dataset"})

    def test_flush_after_timeout(self):
        libhoney.init()
        with requests_mock.Mocker() as m:
            m.post("http://urlme/1/batch/dataset",
                   text=json.dumps(100 * [{"status": 202}]), status_code=200,
                   request_headers={"X-Honeycomb-Team": "writeme"})

            t = transmission.Transmission(
                max_concurrent_batches=1, send_frequency=0.1, gzip_enabled=False)
            t.start()

            ev = libhoney.Event()
            ev.writekey = "writeme"
            ev.dataset = "dataset"
            ev.add_field("key", "value")
            ev.api_host = "http://urlme/"

            t.send(ev)

            time.sleep(0.2)
            resp = t.responses.get()
            assert resp["status_code"] == 202
            t.close()


class TestFileTransmissionSend(unittest.TestCase):
    def test_send(self):
        t = transmission.FileTransmission(user_agent_addition='test')
        t._output = mock.Mock()
        ev = mock.Mock()
        ev.fields.return_value = {'abc': 1, 'xyz': 2}
        ev.sample_rate = 2.0
        ev.dataset = "exciting-dataset!"
        ev.user_agent = f"libhoney-py/{VERSION} test python/{python_version()}"
        ev.created_at = datetime.datetime.now()

        expected_event_time = ev.created_at.isoformat()
        if ev.created_at.tzinfo is None:
            expected_event_time += "Z"

        expected_payload = {
            "data": {'abc': 1, 'xyz': 2},
            "samplerate": 2.0,
            "dataset": "exciting-dataset!",
            "time": expected_event_time,
            "user_agent": ev.user_agent,
        }
        t.send(ev)
        # hard to compare json because dict ordering is not determanistic,
        # so convert back to dict
        args, _ = t._output.write.call_args
        actual_payload = json.loads(args[0])
        self.assertDictEqual(actual_payload, expected_payload)

    def test_send_datetime_value(self):
        t = transmission.FileTransmission(user_agent_addition='test')
        t._output = mock.Mock()
        ev = mock.Mock()
        dt = datetime.datetime.now()
        ev.fields.return_value = {'abc': 1, 'xyz': 2, 'dt': dt}
        ev.sample_rate = 2.0
        ev.dataset = "exciting-dataset!"
        ev.user_agent = f"libhoney-py/{VERSION} test python/{python_version()}"
        ev.created_at = datetime.datetime.now()

        expected_event_time = ev.created_at.isoformat()
        if ev.created_at.tzinfo is None:
            expected_event_time += "Z"

        expected_payload = {
            "data": {'abc': 1, 'xyz': 2, 'dt': str(dt)},
            "samplerate": 2.0,
            "dataset": "exciting-dataset!",
            "time": expected_event_time,
            "user_agent": ev.user_agent,
        }
        t.send(ev)
        # hard to compare json because dict ordering is not determanistic,
        # so convert back to dict
        args, _ = t._output.write.call_args
        actual_payload = json.loads(args[0])
        self.assertDictEqual(actual_payload, expected_payload)
