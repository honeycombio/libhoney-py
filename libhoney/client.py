from six.moves import queue

from libhoney.event import Event
from libhoney.builder import Builder
from libhoney.fields import FieldHolder
from libhoney.transmission import Transmission

class Client(object):
    '''Instantiate a libhoney Client that can prepare and send events to Honeycomb.

    Note that libhoney Clients initialize a number of threads to handle
    sending payloads to Honeycomb. Client initialization is heavy, and re-use
    of Client objects is encouraged. If you must use multiple clients, consider
    reducing `max_concurrent_batches` to reduce the number of threads per client.

    When using a Client instance, you need to use the Client to generate Event and Builder
    objects. Examples:

    ```
    c = Client(writekey="mywritekey", dataset="mydataset")
    ev = c.new_event()
    ev.add_field("foo", "bar")
    ev.send()
    ```

    ```
    c = Client(writekey="mywritekey", dataset="mydataset")
    b = c.new_builder()
    b.add_field("foo", "bar")
    ev = b.new_event()
    ev.send()
    ```

    To ensure that events are flushed before program termination, you should explicitly call `close()`
    on your Client instance.

    Args:

    - `writekey`: the authorization key for your team on Honeycomb. Find your team
            write key at [https://ui.honeycomb.io/account](https://ui.honeycomb.io/account)
    - `dataset`: the name of the default dataset to which to write
    - `sample_rate`: the default sample rate. 1 / `sample_rate` events will be sent.
    - `max_concurrent_batches`: the maximum number of concurrent threads sending events.
    - `max_batch_size`: the maximum number of events to batch before sending.
    - `send_frequency`: how long to wait before sending a batch of events, in seconds.
    - `block_on_send`: if true, block when send queue fills. If false, drop
            events until there's room in the queue
    - `block_on_response`: if true, block when the response queue fills. If
            false, drop response objects.
    - `transmission_impl`: if set, override the default transmission implementation
            (for example, TornadoTransmission)
    - `user_agent_addition`: if set, its contents will be appended to the
            User-Agent string, separated by a space. The expected format is
            product-name/version, eg "myapp/1.0"
    '''
    def __init__(self, writekey="", dataset="", sample_rate=1,
                 api_host="https://api.honeycomb.io",
                 max_concurrent_batches=10, max_batch_size=100,
                 send_frequency=0.25, block_on_send=False,
                 block_on_response=False, transmission_impl=None,
                 user_agent_addition='', debug=False):

        self.xmit = transmission_impl
        if self.xmit is None:
            self.xmit = Transmission(
                max_concurrent_batches=max_concurrent_batches, block_on_send=block_on_send, block_on_response=block_on_response,
                user_agent_addition=user_agent_addition, debug=debug,
            )

        self.xmit.start()
        self.writekey = writekey
        self.dataset = dataset
        self.api_host = api_host
        self.sample_rate = sample_rate
        self._responses = self.xmit.get_response_queue()
        self.block_on_response = block_on_response

        self.fields = FieldHolder()

        self.debug = debug
        if debug:
            self._init_logger()

        self.log('initialized honeycomb client: writekey=%s dataset=%s',
                 writekey, dataset)
        if not writekey:
            self.log('writekey not set! set the writekey if you want to send data to honeycomb')
        if not dataset:
            self.log('dataset not set! set a value for dataset if you want to send data to honeycomb')

    # enable use in a context manager
    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        '''Clean up Transmission if client gets garbage collected'''
        self.close()

    def _init_logger(self):
        import logging
        self._logger = logging.getLogger('honeycomb-sdk')
        self._logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

    def log(self, msg, *args, **kwargs):
        if self.debug:
            self._logger.debug(msg, *args, **kwargs)

    def responses(self):
        '''Returns a queue from which you can read a record of response info from
        each event sent. Responses will be dicts with the following keys:

        - `status_code` - the HTTP response from the api (eg. 200 or 503)
        - `duration` - how long it took to POST this event to the api, in ms
        - `metadata` - pass through the metadata you added on the initial event
        - `body` - the content returned by API (will be empty on success)
        - `error` - in an error condition, this is filled with the error message

        When the Client's `close` method is called, a None will be inserted on
        the queue, indicating that no further responses will be written.
        '''
        return self._responses

    def add_field(self, name, val):
        '''add a global field. This field will be sent with every event.'''
        self.fields.add_field(name, val)

    def add_dynamic_field(self, fn):
        '''add a global dynamic field. This function will be executed every time an
        event is created. The key/value pair of the function's name and its
        return value will be sent with every event.'''
        self.fields.add_dynamic_field(fn)

    def add(self, data):
        '''add takes a mappable object and adds each key/value pair to the
        global scope'''
        self.fields.add(data)

    def send(self, event):
        '''Enqueues the given event to be sent to Honeycomb.

        Should not be called directly. Instead, use Event:
            ev = client.new_event()
            ev.add(data)
            ev.send()
        '''
        if self.xmit is None:
            self.log(
                "tried to send on a closed or uninitialized libhoney client,"
                " ev = %s", event.fields())
            return

        self.log("send enqueuing event ev = %s", event.fields())
        self.xmit.send(event)

    def send_now(self, data):
        '''
        DEPRECATED - This will likely be removed in a future major version.

        Creates an event with the data passed in and enqueues it to be sent.
        Contrary to the name, it does not block the application when called.

        Shorthand for:

            ev = client.new_event()
            ev.add(data)
            ev.send()
        '''
        ev = self.new_event()
        ev.add(data)
        self.log("send_now enqueuing event ev = %s", ev.fields())
        ev.send()

    def send_dropped_response(self, event):
        '''push the dropped event down the responses queue'''
        response = {
            "status_code": 0,
            "duration": 0,
            "metadata": event.metadata,
            "body": "",
            "error": "event dropped due to sampling",
        }
        self.log("enqueuing response = %s", response)
        try:
            if self.block_on_response:
                self._responses.put(response)
            else:
                self._responses.put_nowait(response)
        except queue.Full:
            pass

    def close(self):
        '''Wait for in-flight events to be transmitted then shut down cleanly.
        Optional (will be called automatically at exit) unless your
        application is consuming from the responses queue and needs to know
        when all responses have been received.'''

        if self.xmit:
            self.xmit.close()

        # we should error on post-close sends
        self.xmit = None


    def flush(self):
        '''Closes and restarts the transmission, sending all events. Use this
        if you want to perform a blocking send of all events in your
        application.

        Note: does not work with asynchronous Transmission implementations such
        as TornadoTransmission.
        '''
        if self.xmit and isinstance(self.xmit, Transmission):
            self.xmit.close()
            self.xmit.start()

    def new_event(self, data={}):
        '''Return an Event, initialized to be sent with this client'''
        ev = Event(data=data, client=self)
        return ev

    def new_builder(self, data=None, dyn_fields=None, fields=None):
        '''Return a Builder. Events built from this builder will be sent with
        this client'''
        if data is None:
            data = {}
        if dyn_fields is None:
            dyn_fields = []
        if fields is None:
            fields = FieldHolder()
        builder = Builder(data, dyn_fields, fields, self)
        return builder
