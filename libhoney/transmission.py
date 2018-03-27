'''Transmission handles colleting and sending individual events to Honeycomb'''

from six.moves import queue
from six.moves.urllib.parse import urljoin
import threading
import requests
import statsd
import time
import collections
import concurrent.futures

VERSION = "unset"  # set by libhoney


destination = collections.namedtuple("destination",
                                     ["writekey", "dataset", "api_host"])


class Transmission():
    def __init__(self, max_concurrent_batches=10, block_on_send=False,
                 block_on_response=False, max_batch_size=100, send_frequency=0.25):
        self.max_concurrent_batches = max_concurrent_batches
        self.block_on_send = block_on_send
        self.block_on_response = block_on_response
        self.max_batch_size = max_batch_size
        self.send_frequency = send_frequency

        session = requests.Session()
        session.headers.update({"User-Agent": "libhoney-py/"+VERSION})
        self.session = session

        # libhoney adds events to the pending queue for us to send
        self.pending = queue.Queue(maxsize=1000)
        # we hand back responses from the API on the responses queue
        self.responses = queue.Queue(maxsize=2000)

        self._sending_thread = None
        self.sd = statsd.StatsClient(prefix="libhoney")

    def start(self):
        self._sending_thread = threading.Thread(target=self._sender)
        self._sending_thread.daemon = True
        self._sending_thread.start()

    def send(self, ev):
        '''send accepts an event and queues it to be sent'''
        self.sd.gauge("queue_length", self.pending.qsize())
        try:
            if self.block_on_send:
                self.pending.put(ev)
            else:
                self.pending.put_nowait(ev)
            self.sd.incr("messages_queued")
        except queue.Full:
            response = {
                "status_code": 0,
                "duration": 0,
                "metadata": ev.metadata,
                "body": "",
                "error": "event dropped; queue overflow",
            }
            if self.block_on_response:
                self.responses.put(response)
            else:
                try:
                    self.responses.put_nowait(response)
                except queue.Full:
                    # if the response queue is full when trying to add an event
                    # queue is full response, just skip it.
                    pass
            self.sd.incr("queue_overflow")

    def _sender(self):
        '''_sender is the control loop that pulls events off the `self.pending`
        queue and submits batches for actual sending. '''
        events = []
        last_flush = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_batches) as pool:
            while True:
                try:
                    ev = self.pending.get(timeout=self.send_frequency)
                    if ev is None:
                        # signals shutdown
                        pool.submit(self._flush, events)
                        pool.shutdown()
                        return
                    events.append(ev)
                    if (len(events) > self.max_batch_size or
                            time.time() - last_flush > self.send_frequency):
                        pool.submit(self._flush, events)
                        events = []
                        last_flush = time.time()
                except queue.Empty:
                    pool.submit(self._flush, events)
                    events = []
                    last_flush = time.time()

    def _flush(self, events):
        if not events:
            return
        for dest, group in group_events_by_destination(events).items():
            self._send_batch(dest, group)

    def _send_batch(self, destination, events):
        ''' Makes a single batch API request with the given list of events. The
        `destination` argument contains the write key, API host and dataset
        name used to build the request.'''
        start = time.time()
        status_code = 0
        try:
            url = urljoin(urljoin(destination.api_host, "/1/batch/"),
                          destination.dataset)
            payload = []
            for ev in events:
                event_time = ev.created_at.isoformat()
                if ev.created_at.tzinfo is None:
                    event_time += "Z"
                payload.append({
                    "time": event_time,
                    "samplerate": ev.sample_rate,
                    "data": ev.fields()})
            resp = self.session.post(
                url,
                headers={"X-Honeycomb-Team": destination.writekey},
                json=payload)
            status_code = resp.status_code
            resp.raise_for_status()
            statuses = [d["status"] for d in resp.json()]
            for ev, status in zip(events, statuses):
                self._enqueue_response(status, "", None, start, ev.metadata)
                self.sd.incr("messages_sent")
        except Exception as e:
            # Catch all exceptions and hand them to the responses queue.
            self._enqueue_errors(status_code, e, start, events)

    def _enqueue_errors(self, status_code, error, start, events):
        for ev in events:
            self.sd.incr("send_errors")
            self._enqueue_response(status_code, "", error, start, ev.metadata)

    def _enqueue_response(self, status_code, body, error, start, metadata):
        resp = {
            "status_code": status_code,
            "body": body,
            "error": error,
            "duration": (time.time() - start) * 1000,
            "metadata": metadata
        }
        if self.block_on_response:
            self.responses.put(resp)
        else:
            try:
                self.responses.put_nowait(resp)
            except queue.Full:
                pass

    def close(self):
        '''call close to send all in-flight requests and shut down the
            senders nicely. Times out after max 20 seconds per sending thread
            plus 10 seconds for the response queue'''
        try:
            self.pending.put(None, True, 10)
        except queue.Full:
            pass
        self._sending_thread.join()
        # signal to the responses queue that nothing more is coming.
        try:
            self.responses.put(None, True, 10)
        except queue.Full:
            pass

    def get_response_queue(self):
        ''' return the responses queue on to which will be sent the response
        objects from each event send'''
        return self.responses


def group_events_by_destination(events):
    ''' Events all get added to a single queue when you call send(), but you
    might be sending different events to different datasets. This function
    takes a list of events and groups them by the parameters we need to build
    the API request.'''
    ret = collections.defaultdict(list)
    for ev in events:
        ret[destination(ev.writekey, ev.dataset, ev.api_host)].append(ev)
    return ret
