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
import random
from six.moves.queue import Queue

import libhoney.state as state
from libhoney.client import Client
from libhoney.builder import Builder
from libhoney.event import Event
from libhoney.fields import FieldHolder
from libhoney.errors import SendError

random.seed()


def init(writekey="", dataset="", sample_rate=1,
         api_host="https://api.honeycomb.io", max_concurrent_batches=10,
         max_batch_size=100, send_frequency=0.25,
         block_on_send=False, block_on_response=False, transmission_impl=None,
         debug=False):
    '''Initialize libhoney and prepare it to send events to Honeycomb.

    Note that libhoney initialization initializes a number of threads to handle
    sending payloads to Honeycomb. Be mindful of where you're calling
    `libhoney.init()` in order to ensure correct enqueueing + processing of
    events on the spawned threads.

    Note that this method of initialization will be deprecated in a future
    libhoney version. For new use cases, use `libhoney.Client`.

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
    state.G_CLIENT = Client(
        writekey=writekey,
        dataset=dataset,
        sample_rate=sample_rate,
        api_host=api_host,
        max_concurrent_batches=max_concurrent_batches,
        max_batch_size=max_batch_size,
        send_frequency=send_frequency,
        block_on_send=block_on_send,
        block_on_response=block_on_response,
        transmission_impl=transmission_impl,
        debug=debug,
    )


def responses():
    '''Returns a queue from which you can read a record of response info from
    each event sent. Responses will be dicts with the following keys:

    - `status_code` - the HTTP response from the api (eg. 200 or 503)
    - `duration` - how long it took to POST this event to the api, in ms
    - `metadata` - pass through the metadata you added on the initial event
    - `body` - the content returned by API (will be empty on success)
    - `error` - in an error condition, this is filled with the error message

    When a None object appears on the queue the reader should exit'''
    if state.G_CLIENT is None:
        state.warn_uninitialized()
        # return an empty queue rather than None. While not ideal, it is
        # better than returning None and introducing AttributeErrors into
        # the caller's code
        return Queue()

    return state.G_CLIENT.responses()


def add_field(name, val):
    '''add a global field. This field will be sent with every event.'''
    if state.G_CLIENT is None:
        state.warn_uninitialized()
        return
    state.G_CLIENT.add_field(name, val)


def add_dynamic_field(fn):
    '''add a global dynamic field. This function will be executed every time an
       event is created. The key/value pair of the function's name and its
       return value will be sent with every event.'''
    if state.G_CLIENT is None:
        state.warn_uninitialized()
        return
    state.G_CLIENT.add_dynamic_field(fn)


def add(data):
    '''add takes a mappable object and adds each key/value pair to the global
       scope'''
    if state.G_CLIENT is None:
        state.warn_uninitialized()
        return
    state.G_CLIENT.add(data)

def new_event(data={}):
    ''' Creates a new event with the default client. If libhoney has not been
    initialized, sending this event will be a no-op.
    '''
    return Event(data=data, client=state.G_CLIENT)

def send_now(data):
    '''
    DEPRECATED - This will likely be removed in a future major version.

    Creates an event with the data passed in and enqueues it to be sent.
    Contrary to the name, it does not block the application when called.

    Shorthand for:

        ev = Event()
        ev.add(data)
        ev.send()
    '''
    if state.G_CLIENT is None:
        state.warn_uninitialized()
        return
    ev = Event(client=state.G_CLIENT)
    ev.add(data)
    ev.send()

def flush():
    '''Closes and restarts the transmission, sending all events. Use this
    if you want to perform a blocking send of all events in your
    application.

    Note: does not work with asynchronous Transmission implementations such
    as TornadoTransmission.
    '''
    if state.G_CLIENT:
        state.G_CLIENT.flush()

def close():
    '''Wait for in-flight events to be transmitted then shut down cleanly.
       Optional (will be called automatically at exit) unless your
       application is consuming from the responses queue and needs to know
       when all responses have been received.'''
    if state.G_CLIENT:
        state.G_CLIENT.close()

    # we should error on post-close sends
    state.G_CLIENT = None

atexit.register(close) # safe because it's a no-op unless init() was called

# export everything
__all__ = [
    "Builder", "Event", "Client", "FieldHolder",
    "SendError", "add", "add_dynamic_field",
    "add_field", "close", "init", "responses", "send_now",
]
