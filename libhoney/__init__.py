'''libhoney is a library to allow you to send events to Honeycomb from within
your python application.

Basic usage:

- initialize libhoney with your Honeycomb writekey and dataset name
- create an event object and populate it with fields
- send the event object
- close libhoney when your program is finished

Sending on a closed or uninitialized libhoney will throw a `libhoney.SendError`
exception.

You can find an example demonstrating usage in example.py'''

import atexit
import datetime
from contextlib import contextmanager
import json
from libhoney import transmission, trace
import inspect
import random
from six.moves import queue
from libhoney.version import VERSION

# global transmit instance will be held by _xmit
_xmit = None

g_writekey = ""
g_dataset = ""
g_api_host = ""
g_sample_rate = 1
g_responses = queue.Queue(maxsize=1)
g_block_on_response = False
g_tracer = None

transmission.VERSION = VERSION

random.seed()


def init(writekey="", dataset="", sample_rate=1,
         api_host="https://api.honeycomb.io", max_concurrent_batches=10,
         max_batch_size=100, send_frequency=0.25,
         block_on_send=False, block_on_response=False, transmission_impl=None):
    '''Initialize libhoney and prepare it to send events to Honeycomb.

    Note that libhoney initialization initializes a number of threads to handle
    sending payloads to Honeycomb. Be mindful of where you're calling
    `libhoney.init()` in order to ensure correct enqueueing + processing of
    events on the spawned threads.


    Args:

    - `writekey`: the authorization key for your team on Honeycomb. Find your team
            write key at [https://ui.honeycomb.io/account](https://ui.honeycomb.io/account)
    - `dataset`: the name of the default dataset to which to write
    - `sample_rate`: the default sample rate. 1 / `sample_rate` events will be sent.
    - `max_concurrent_batches`: the maximum number of concurrent threads sending events.
    - `max_batch_size`: the maximum number of events to batch before sendinga.
    - `send_frequency`: how long to wait before sending a batch of events, in seconds.
    - `block_on_send`: if true, block when send queue fills. If false, drop
            events until there's room in the queue
    - `block_on_response`: if true, block when the response queue fills. If
            false, drop response objects.
    - `transmission_impl`: if set, override the default transmission implementation (for example, TornadoTransmission)

    --------

    **Configuration recommendations**:

    **For gunicorn**, use a [`post_worker_init` config hook](http://docs.gunicorn.org/en/stable/settings.html#post-worker-init) to initialize Honeycomb:

        # conf.py
        import logging
        import os

        def post_worker_init(worker):
            logging.info(f'libhoney initialization in process pid {os.getpid()}')
            libhoney.init(writekey="YOUR_WRITE_KEY", dataset="dataset_name")

    Then start gunicorn with the `-c` option:

        gunicorn -c /path/to/conf.py
    '''
    global _xmit, g_writekey, g_dataset, g_api_host, g_sample_rate, g_responses, g_tracer
    global g_block_on_response
    _xmit = transmission_impl
    if _xmit is None:
        _xmit = transmission.Transmission(max_concurrent_batches, block_on_send,
                                        block_on_response)
    _xmit.start()
    g_writekey = writekey
    g_dataset = dataset
    g_api_host = api_host
    g_sample_rate = sample_rate
    g_responses = _xmit.get_response_queue()
    g_block_on_response = block_on_response
    g_tracer = trace.Tracer(sample_rate=sample_rate)


def responses():
    '''Returns a queue from which you can read a record of response info from
    each event sent. Responses will be dicts with the following keys:

    - `status_code` - the HTTP response from the api (eg. 200 or 503)
    - `duration` - how long it took to POST this event to the api, in ms
    - `metadata` - pass through the metadata you added on the initial event
    - `body` - the content returned by API (will be empty on success)
    - `error` - in an error condition, this is filled with the error message

    When a None object appears on the queue the reader should exit'''
    global g_responses
    return g_responses


def add_field(name, val):
    '''add a global field. This field will be sent with every event.'''
    _fields.add_field(name, val)


def add_dynamic_field(fn):
    '''add a global dynamic field. This function will be executed every time an
       event is created. The key/value pair of the function's name and its
       return value will be sent with every event.'''
    _fields.add_dynamic_field(fn)


def add(data):
    '''add takes a mappable object and adds each key/value pair to the global
       scope'''
    _fields.add(data)


def send_now(data):
    '''creates an event with the data passed in and sends it immediately.

    Shorthand for:

        ev = Event()
        ev.add(data)
        ev.send()
   '''
    ev = Event()
    ev.add(data)
    ev.send()


def close():
    '''Wait for in-flight events to be transmitted then shut down cleanly.
       Optional (will be called automatically at exit) unless your
       application is consuming from the responses queue and needs to know
       when all responses have been received.'''
    global _xmit

    # if libhoney was never initialized, don't try to close it
    if _xmit:
        _xmit.close()

    # we should error on post-close sends
    _xmit = None

def trace_call(fn, *args, service_name="", trace_name="", trace_context=None, trace_id="", **kwargs):
    '''Wraps the call to enable tracing in libhoney. If this is the first trace
    in the call stack, a new trace_id will be generated. Subsequent wrapped
    calls will be linked back to the parent trace_id and span_ids all the way
    down the stack.

    - `fn` - the function that you want to wrap
    - `*args` - any positional arguments to the wrapped function
    - `service_name` - optional - name for your service. will show up in the trace UI
    - `trace_name` - optional - the name for this call. If not set, will default to
          function name
    - `trace_context` - optional - a dictionary of any fields you would like to
          append to the event
    - `trace_id` - optional - if set, will use a specific trace_id. Set this
          if you have already generated a trace ID
    - `**kwargs` - any keyword args to the wrapped function
    '''
    return g_tracer.trace_call(fn, *args, service_name=service_name, trace_name=trace_name,
                               trace_context=trace_context, trace_id=trace_id, **kwargs)

atexit.register(close) # safe because it's a no-op unless init() was called


class FieldHolder:
    '''A FieldHolder is the generalized class that stores fields and dynamic
       fields. It should not be used directly; only through the subclasses'''

    def __init__(self):
        self._data = {}
        self._dyn_fields = set()

    def __add__(self, other):
        '''adding two field holders merges the data with other overriding
           any fields they have in common'''
        self._data.update(other._data)
        self._dyn_fields.update(other._dyn_fields)
        return self

    def __eq__(self, other):
        '''two FieldHolders are equal if their datasets are equal'''
        return ((self._data, self._dyn_fields) ==
                (other._data, other._dyn_fields))

    def __ne__(self, other):
        '''two FieldHolders are equal if their datasets are equal'''
        return not self.__eq__(other)

    def add_field(self, name, val):
        self._data[name] = val

    def add_dynamic_field(self, fn):
        if not inspect.isroutine(fn):
            raise TypeError("add_dynamic_field requires function argument")
        self._dyn_fields.add(fn)

    def add(self, data):
        try:
            for k, v in data.items():
                self.add_field(k, v)
        except AttributeError:
            raise TypeError("add requires a dict-like argument")

    def is_empty(self):
        '''returns true if there is no data in this FieldHolder'''
        return len(self._data) == 0

    def __str__(self):
        '''returns a JSON blob of the fields in this holder'''
        return json.dumps(self._data)

_fields = FieldHolder()


class Builder(object):
    '''A Builder is a scoped object to which you can add fields and dynamic
       fields. Events created from this builder will inherit all fields
       and dynamic fields from this builder and the global environment'''

    def __init__(self, data={}, dyn_fields=[], fields=FieldHolder()):
        self._fields = FieldHolder()  # get an empty FH
        self._fields += _fields       # fill it with the global state
        self._fields.add(data)        # and anything passed in
        [self._fields.add_dynamic_field(fn) for fn in dyn_fields]
        self._fields += fields
        self.writekey = g_writekey
        self.dataset = g_dataset
        self.api_host = g_api_host
        self.sample_rate = g_sample_rate

    def add_field(self, name, val):
        self._fields.add_field(name, val)

    def add_dynamic_field(self, fn):
        '''`add_dynamic_field` adds a function to the builder. When you create an
           event from this builder, the function will be executed. The function
           name is the key and it should return one value.'''
        self._fields.add_dynamic_field(fn)

    def add(self, data):
        '''add takes a dict-like object and adds each key/value pair to the
           builder.'''
        self._fields.add(data)

    def send_now(self, data):
        '''creates an event from this builder with the data passed in and sends
           it immediately. Shorthand for
           `ev = builder.new_event(); ev.add(data); ev.send()`'''
        ev = self.new_event()
        ev.add(data)
        ev.send()

    def new_event(self):
        '''creates a new event from this builder, inheriting all fields and
           dynamic fields present in the builder'''
        ev = Event(fields=self._fields)
        ev.writekey = self.writekey
        ev.dataset = self.dataset
        ev.api_host = self.api_host
        ev.sample_rate = self.sample_rate
        return ev

    def clone(self):
        '''creates a new builder from this one, creating its own scope to
           which additional fields and dynamic fields can be added.'''
        c = Builder(fields=self._fields)
        c.writekey = self.writekey
        c.dataset = self.dataset
        c.sample_rate = self.sample_rate
        return c


class Event(object):
    '''An Event is a collection of fields that will be sent to Honeycomb.'''

    def __init__(self, data={}, dyn_fields=[], fields=FieldHolder()):
        # populate the event's fields
        self._fields = FieldHolder()  # get an empty FH
        self._fields += _fields       # fill it with the global state
        self._fields.add(data)        # and anything passed in
        [self._fields.add_dynamic_field(fn) for fn in dyn_fields]
        self._fields += fields
        # fill in other info
        self.created_at = datetime.datetime.utcnow()
        self.writekey = g_writekey
        self.dataset = g_dataset
        self.api_host = g_api_host
        self.sample_rate = g_sample_rate
        self.metadata = None
        # execute all the dynamic functions and add their data
        for fn in self._fields._dyn_fields:
            self._fields.add_field(fn.__name__, fn())

    def add_field(self, name, val):
        self._fields.add_field(name, val)

    def add_metadata(self, md):
        '''Add metadata to an event. This metadata is handed back to you in
        the response queue. It is not transmitted to Honeycomb; it is a place
        for you to put identifying information to understand which event a
        response queue object represents.'''
        self.metadata = md

    def add(self, data):
        self._fields.add(data)

    @contextmanager
    def timer(self, name):
        '''timer is a context for timing (in milliseconds) a function call.

        Example:

            ev = Event()
            with ev.timer("database_dur_ms"):
                do_database_work()

           will add a field (name, duration) indicating how long it took to run
           do_database_work()'''
        start = datetime.datetime.now()
        yield
        duration = datetime.datetime.now() - start
        # report in ms
        self.add_field(name, duration.total_seconds() * 1000)

    def send(self):
        '''send queues this event for transmission to Honeycomb.

        Raises a SendError exception when called with an uninitialized
        libhoney. Will drop sampled events when sample_rate > 1,
        and ensure that the Honeycomb datastore correctly considers it
        as representing `sample_rate` number of similar events.'''
        global _xmit
        if _xmit is None:
            # do this in addition to below to error even when sampled
            raise SendError(
                "Tried to send on a closed or uninitialized libhoney")
        if _should_drop(self.sample_rate):
            _send_dropped_response(self)
            return
        self.send_presampled()

    def send_presampled(self):
        '''send_presampled queues this event for transmission to Honeycomb.

        Caller is responsible for sampling logic - will not drop any events
        for sampling. Defining a `sample_rate` will ensure that the Honeycomb
        datastore correctly considers it as representing `sample_rate` number
        of similar events.'''
        global _xmit
        if _xmit is None:
            raise SendError(
                "Tried to send on a closed or uninitialized libhoney")
        if self._fields.is_empty():
            raise SendError(
                "No metrics added to event. Won't send empty event.")
        if self.api_host == "":
            raise SendError(
                "No api_host for Honeycomb. Can't send to the Great Unknown.")
        if self.writekey == "":
            raise SendError(
                "No write_key specified. Can't send event.")
        if self.dataset == "":
            raise SendError(
                "No dataset for Honeycomb. Can't send event without knowing which dataset it belongs to.")
        _xmit.send(self)

    def __str__(self):
        return str(self._fields)

    def fields(self):
        return self._fields._data


def _should_drop(rate):
    '''returns true if the sample should be dropped'''
    return random.randint(1, rate) != 1


def _send_dropped_response(ev):
    '''push the dropped event down the responses queue'''
    response = {
        "status_code": 0,
        "duration": 0,
        "metadata": ev.metadata,
        "body": "",
        "error": "event dropped due to sampling",
    }
    try:
        if g_block_on_response:
            g_responses.put(response)
        else:
            g_responses.put_nowait(response)
    except queue.Full:
        pass


class SendError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
