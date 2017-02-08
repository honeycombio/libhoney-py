'''Transmission handles colleting and sending individual events to Honeycomb'''

from six.moves import queue
from urlparse import urljoin
import threading
import requests
import statsd
import datetime

sd = statsd.StatsClient(prefix="libhoney")
VERSION = "unset"  # set by libhoney


class Transmission():

    def __init__(self, max_concurrent_batches=10, block_on_send=False,
                 block_on_response=False):
        self.max_concurrent_batches = max_concurrent_batches
        self.block_on_send = block_on_send
        self.block_on_response = block_on_response

        session = requests.Session()
        session.headers.update({"User-Agent": "libhoney-py/"+VERSION})
        self.session = session

        # libhoney adds events to the pending queue for us to send
        self.pending = queue.Queue(maxsize=1000)
        # we hand back responses from the API on the responses queue
        self.responses = queue.Queue(maxsize=2000)

        self.threads = []
        for i in range(self.max_concurrent_batches):
            t = threading.Thread(target=self._sender)
            t.start()
            self.threads.append(t)

    def send(self, ev):
        '''send accepts an event and queues it to be sent'''
        sd.gauge("queue_length", self.pending.qsize())
        try:
            if self.block_on_send:
                self.pending.put(ev)
            else:
                self.pending.put_nowait(ev)
            sd.incr("messages_queued")
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
                self.responses.put_nowait(response)
            sd.incr("queue_overflow")

    def _sender(self):
        '''_sender is the control loop for each sending thread'''
        while True:
            ev = self.pending.get()
            if ev is None:
                break
            self._send(ev)

    def _send(self, ev):
        '''_send should only be called from sender and sends an individual
            event to Honeycomb'''
        start = get_now()
        url = urljoin(urljoin(ev.api_host, "/1/events/"), ev.dataset)
        req = requests.Request('POST', url, data=str(ev))
        event_time = ev.created_at.isoformat()
        if ev.created_at.tzinfo is None:
            event_time += "Z"
        req.headers.update({
            "X-Event-Time": event_time,
            "X-Honeycomb-Team": ev.writekey,
            "X-Honeycomb-SampleRate": str(ev.sample_rate)})
        preq = self.session.prepare_request(req)
        resp = self.session.send(preq)
        if (resp.status_code == 200):
            sd.incr("messages_sent")
        else:
            sd.incr("send_errors")
        dur = get_now() - start
        response = {
            "status_code": resp.status_code,
            "duration": dur.total_seconds() * 1000,  # report in milliseconds
            "metadata": ev.metadata,
            "body": resp.text,
            "error": "",
        }
        try:
            if self.block_on_response:
                self.responses.put(response)
            else:
                self.responses.put_nowait(response)
        except queue.Full:
            pass

    def close(self):
        '''call close to send all in-flight requests and shut down the
           senders nicely'''
        for i in range(self.max_concurrent_batches):
            self.pending.put(None)
        for t in self.threads:
            t.join()
        # signal to the responses queue that nothing more is coming.
        self.responses.put(None)

    def get_response_queue(self):
        ''' return the responses queue on to which will be sent the response
        objects from each event send'''
        return self.responses

def get_now():
    return datetime.datetime.now()
