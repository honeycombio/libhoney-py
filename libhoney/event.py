import datetime
import random
from contextlib import contextmanager

import libhoney.state as state
from libhoney.fields import FieldHolder


class Event(object):
    '''An Event is a collection of fields that will be sent to Honeycomb.'''

    def __init__(self, data={}, dyn_fields=[], fields=FieldHolder(), client=None):
        if client is None:
            client = state.G_CLIENT

        # copy configuration from client
        self.client = client
        if self.client:
            self.writekey = client.writekey
            self.dataset = client.dataset
            self.api_host = client.api_host
            self.sample_rate = client.sample_rate
        else:
            self.writekey = None
            self.dataset = None
            self.api_host = 'https://api.honeycomb.io'
            self.sample_rate = 1

        # populate the event's fields
        self._fields = FieldHolder()  # get an empty FH
        if self.client:
            self._fields += self.client.fields # fill it with the client fields
        self._fields.add(data)        # and anything passed in
        [self._fields.add_dynamic_field(fn) for fn in dyn_fields]
        self._fields += fields

        # fill in other info
        self.created_at = datetime.datetime.utcnow()
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

        Will drop sampled events when sample_rate > 1,
        and ensure that the Honeycomb datastore correctly considers it
        as representing `sample_rate` number of similar events.'''
        # warn if we're not using a client instance and global libhoney
        # is not initialized. This will result in a noop, but is better
        # than crashing the caller if they forget to initialize
        if self.client is None:
            state.warn_uninitialized()
            return

        if _should_drop(self.sample_rate):
            self.client.send_dropped_response(self)
            return

        self.send_presampled()

    def send_presampled(self):
        '''send_presampled queues this event for transmission to Honeycomb.

        Caller is responsible for sampling logic - will not drop any events
        for sampling. Defining a `sample_rate` will ensure that the Honeycomb
        datastore correctly considers it as representing `sample_rate` number
        of similar events.

        Raises SendError if no fields are defined or critical attributes not
        set (writekey, dataset, api_host).'''
        if self._fields.is_empty():
            self.client.log("No metrics added to event. Won't send empty event.")
            return
        if self.api_host == "":
            self.client.log("No api_host for Honeycomb. Can't send to the Great Unknown.")
            return
        if self.writekey == "":
            self.client.log("No writekey specified. Can't send event.")
            return
        if self.dataset == "":
            self.client.log(
                "No dataset for Honeycomb. Can't send event without knowing which dataset it belongs to.")
            return

        if self.client:
            self.client.send(self)
        else:
            state.warn_uninitialized()

    def __str__(self):
        return str(self._fields)

    def fields(self):
        return self._fields._data

def _should_drop(rate):
    '''returns true if the sample should be dropped'''
    return random.randint(1, rate) != 1