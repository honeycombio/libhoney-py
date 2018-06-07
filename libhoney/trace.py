import datetime
import hashlib
import inspect
import math
import struct
import uuid

import libhoney

MAX_INT32 = math.pow(2, 32) - 1

class Tracer(object):
    def __init__(self, sample_rate=1.0):
        self.trace_ids = {}
        self.span_ids = {}
        self.sample_upper_bound = MAX_INT32 / sample_rate

    def _get_parent_span(self, frame):
        ''' determine if a frame up the stack has a span_id '''
        # skip the current frame, and look for a previous frame with a span_id
        frame = frame.f_back
        
        while frame:
            if id(frame) in self.span_ids:
                return frame
            frame = frame.f_back

        return None

    def _should_sample(self, trace_id):
        # compute a sha1
        sha1 = hashlib.sha1()
        sha1.update(trace_id.encode('utf-8'))
        # convert last 4 digits to int
        value, = struct.unpack('<I', sha1.digest()[-4:])
        return value < self.sample_upper_bound

    def trace_call(self, fn, *args, service_name="", trace_name="", trace_context=None, trace_id="", **kwargs):
        current_frame = inspect.currentframe()
        parent = self._get_parent_span(current_frame)

        # we're the first span, generate trace ID AND span ID
        if parent is None:
            # if the trace ID has been passed in, do not generate a new one
            if not trace_id:
                trace_id = _new_id()
            
            self.trace_ids[id(current_frame)] = trace_id
            self.span_ids[id(current_frame)] = _new_id()
            parent_span_id = None
        else:
            self.trace_ids[id(current_frame)] = self.trace_ids[id(parent)]
            self.span_ids[id(current_frame)] = _new_id()
            parent_span_id = self.span_ids[id(parent)]

        # once we know the trace ID of this frame, we can decide if we should
        # sample it
        should_sample = self._should_sample(self.trace_ids[id(current_frame)])

        if should_sample:
            time_start = datetime.datetime.now()
            ev = libhoney.Event()

        try:
            ret = fn(*args, **kwargs)
        finally:
            if should_sample:
                duration = datetime.datetime.now() - time_start
                duration_ms = duration.total_seconds() * 1000.0

                if not trace_name:
                    trace_name = fn.__name__

                if trace_context is None:
                    trace_context = {}
                trace_context["trace.trace_id"] = self.trace_ids[id(current_frame)]
                trace_context["trace.span_id"] = self.span_ids[id(current_frame)]
                trace_context["trace.parent_id"] = parent_span_id
                trace_context["duration_ms"] = duration_ms
                trace_context["name"] = trace_name
                if service_name:
                    trace_context["service_name"] = service_name
                ev.add(trace_context)
                ev.send_presampled()

            # clean up our dicts when we exit the span
            del self.span_ids[id(current_frame)]
            del self.trace_ids[id(current_frame)]

        return ret

def _new_id():
    return str(uuid.uuid4())
