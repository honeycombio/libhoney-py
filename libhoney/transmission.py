'''Transmission handles colleting and sending individual events to Honeycomb'''

from six.moves import queue
from six.moves.urllib.parse import urljoin
import json
import threading
import requests
import statsd
import sys
import time
import collections
import concurrent.futures
from libhoney.version import VERSION

try:
    from tornado import ioloop, gen
    from tornado.httpclient import AsyncHTTPClient, HTTPRequest
    from tornado.locks import Semaphore
    from tornado.queues import Queue, QueueFull
    from tornado.util import TimeoutError
    has_tornado = True
except ImportError:
    has_tornado = False

destination = collections.namedtuple("destination",
                                     ["writekey", "dataset", "api_host"])

class Transmission():
    def __init__(self, max_concurrent_batches=10, block_on_send=False,
                 block_on_response=False, max_batch_size=100, send_frequency=0.25,
                 user_agent_addition='', debug=False):
        self.max_concurrent_batches = max_concurrent_batches
        self.block_on_send = block_on_send
        self.block_on_response = block_on_response
        self.max_batch_size = max_batch_size
        self.send_frequency = send_frequency

        user_agent = "libhoney-py/" + VERSION
        if user_agent_addition:
            user_agent += " " + user_agent_addition

        session = requests.Session()
        session.headers.update({"User-Agent": user_agent})
        self.session = session

        # libhoney adds events to the pending queue for us to send
        self.pending = queue.Queue(maxsize=1000)
        # we hand back responses from the API on the responses queue
        self.responses = queue.Queue(maxsize=2000)

        self._sending_thread = None
        self.sd = statsd.StatsClient(prefix="libhoney")

        self.debug = debug
        if debug:
            self._init_logger()

    def _init_logger(self):
        import logging
        self._logger = logging.getLogger('honeycomb-sdk-xmit')
        self._logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

    def log(self, msg, *args, **kwargs):
        if self.debug:
            self._logger.debug(msg, *args, **kwargs)

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

            self.log("firing batch, size = %d", len(payload))
            resp = self.session.post(
                url,
                headers={"X-Honeycomb-Team": destination.writekey, "Content-Type": "application/json"},
                data=json.dumps(payload))
            status_code = resp.status_code
            resp.raise_for_status()
            statuses = [{"status": d.get("status"), "error": d.get("error")} for d in resp.json()]
            for ev, status in zip(events, statuses):
                self._enqueue_response(status.get("status"), "", status.get("error"), start, ev.metadata)

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
        self.log("enqueuing response = %s", resp)
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

# only define this class if tornado exists, otherwise we'll get NameError on gen
# Is there a better way to do this?
if has_tornado:
    class TornadoTransmissionException(Exception):
        pass

    class TornadoTransmission():
        def __init__(self, max_concurrent_batches=10, block_on_send=False,
                    block_on_response=False, max_batch_size=100, send_frequency=0.25,
                    user_agent_addition=''):
            if not has_tornado:
                raise ImportError('TornadoTransmission requires tornado, but it was not found.')

            self.block_on_send = block_on_send
            self.block_on_response = block_on_response
            self.max_batch_size = max_batch_size
            self.send_frequency = send_frequency

            user_agent = "libhoney-py/" + VERSION
            if user_agent_addition:
                user_agent += " " + user_agent_addition

            self.http_client = AsyncHTTPClient(
                force_instance=True,
                defaults=dict(user_agent=user_agent))

            # libhoney adds events to the pending queue for us to send
            self.pending = Queue(maxsize=1000)
            # we hand back responses from the API on the responses queue
            self.responses = Queue(maxsize=2000)

            self.batch_data = {}
            self.sd = statsd.StatsClient(prefix="libhoney")
            self.batch_sem = Semaphore(max_concurrent_batches)

        def start(self):
            ioloop.IOLoop.current().spawn_callback(self._sender)

        def send(self, ev):
            '''send accepts an event and queues it to be sent'''
            self.sd.gauge("queue_length", self.pending.qsize())
            try:
                if self.block_on_send:
                    self.pending.put(ev)
                else:
                    self.pending.put_nowait(ev)
                self.sd.incr("messages_queued")
            except QueueFull:
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
                    except QueueFull:
                        # if the response queue is full when trying to add an event
                        # queue is full response, just skip it.
                        pass
                self.sd.incr("queue_overflow")

        # We're using the older decorator/yield model for compatibility with
        # Python versions before 3.5.
        # See: http://www.tornadoweb.org/en/stable/guide/coroutines.html#python-3-5-async-and-await
        @gen.coroutine
        def _sender(self):
            '''_sender is the control loop that pulls events off the `self.pending`
            queue and submits batches for actual sending. '''
            events = []
            last_flush = time.time()
            while True:
                try:
                    ev = yield self.pending.get(timeout=self.send_frequency)
                    if ev is None:
                        # signals shutdown
                        yield self._flush(events)
                        return
                    events.append(ev)
                    if (len(events) > self.max_batch_size or
                        time.time() - last_flush > self.send_frequency):
                        yield self._flush(events)
                        events = []
                except TimeoutError:
                    yield self._flush(events)
                    events = []
                    last_flush = time.time()

        @gen.coroutine
        def _flush(self, events):
            if not events:
                return
            for dest, group in group_events_by_destination(events).items():
                yield self._send_batch(dest, group)

        @gen.coroutine
        def _send_batch(self, destination, events):
            ''' Makes a single batch API request with the given list of events. The
            `destination` argument contains the write key, API host and dataset
            name used to build the request.'''
            start = time.time()
            status_code = 0

            try:
                # enforce max_concurrent_batches
                yield self.batch_sem.acquire()
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
                req = HTTPRequest(
                    url,
                    method='POST',
                    headers={
                        "X-Honeycomb-Team": destination.writekey,
                        "Content-Type": "application/json",
                    },
                    body=json.dumps(payload),
                )
                self.http_client.fetch(req, self._response_callback)
                # store the events that were sent so we can process responses later
                # it is important that we delete these eventually, or we'll run into memory issues
                self.batch_data[req] = {"start": start, "events": events}
            except Exception as e:
                # Catch all exceptions and hand them to the responses queue.
                self._enqueue_errors(status_code, e, start, events)
            finally:
                self.batch_sem.release()

        def _enqueue_errors(self, status_code, error, start, events):
            for ev in events:
                self.sd.incr("send_errors")
                self._enqueue_response(status_code, "", error, start, ev.metadata)

        def _response_callback(self, resp):
            # resp.request should be the same HTTPRequest object built by _send_batch
            # and mapped to values in batch_data
            events = self.batch_data[resp.request]["events"]
            start  = self.batch_data[resp.request]["start"]
            try:
                status_code = resp.code
                resp.rethrow()

                statuses = [d["status"] for d in json.loads(resp.body)]
                for ev, status in zip(events, statuses):
                    self._enqueue_response(status, "", None, start, ev.metadata)
                    self.sd.incr("messages_sent")
            except Exception as e:
                self._enqueue_errors(status_code, e, start, events)
                self.sd.incr("send_errors")
            finally:
                # clean up the data for this batch
                del self.batch_data[resp.request]

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
                except QueueFull:
                    pass

        def close(self):
            '''call close to send all in-flight requests and shut down the
                senders nicely. Times out after max 20 seconds per sending thread
                plus 10 seconds for the response queue'''
            try:
                self.pending.put(None, 10)
            except QueueFull:
                pass
            # signal to the responses queue that nothing more is coming.
            try:
                self.responses.put(None, 10)
            except QueueFull:
                pass

        def get_response_queue(self):
            ''' return the responses queue on to which will be sent the response
            objects from each event send'''
            return self.responses

class FileTransmission():
    ''' Transmission implementation that writes to a file object
    rather than sending events to Honeycomb. Defaults to STDERR. '''
    def __init__(self, user_agent_addition='', output=sys.stderr):
        self._output = output

        self._user_agent = "libhoney-py/" + VERSION
        if user_agent_addition:
            self._user_agent += " " + user_agent_addition

    def start(self):
        ''' start is defined to be consistent with the Transmission API but
        does nothing '''
        pass

    def send(self, ev):
        '''send accepts an event and writes it to the configured output file'''
        event_time = ev.created_at.isoformat()
        if ev.created_at.tzinfo is None:
            event_time += "Z"

        # we add dataset and user_agent to the payload
        # if processed by another honeycomb agent (i.e. agentless integrations
        # for AWS), this data will get used to route the event to the right
        # location with appropriate metadata
        payload = {
            "time": event_time,
            "samplerate": ev.sample_rate,
            "dataset": ev.dataset,
            "user_agent": self._user_agent,
            "data": ev.fields(),
        }
        self._output.write(json.dumps(payload) + "\n")

    def close(self):
        '''Exists to be consistent with the Transmission API, but does nothing
        '''
        pass

    def flush(self):
        '''Exists to be consistent with the Transmission API, but does nothing
        '''
        self._output.flush()

    def get_response_queue(self):
        '''Not implemented in FileTransmission - you should not attempt to
        inspect the response queue when using this type.'''
        pass

def group_events_by_destination(events):
    ''' Events all get added to a single queue when you call send(), but you
    might be sending different events to different datasets. This function
    takes a list of events and groups them by the parameters we need to build
    the API request.'''
    ret = collections.defaultdict(list)
    for ev in events:
        ret[destination(ev.writekey, ev.dataset, ev.api_host)].append(ev)
    return ret
