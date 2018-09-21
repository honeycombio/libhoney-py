import libhoney.state as state
from libhoney.event import Event
from libhoney.fields import FieldHolder

class Builder(object):
    '''A Builder is a scoped object to which you can add fields and dynamic
       fields. Events created from this builder will inherit all fields
       and dynamic fields from this builder and the global environment'''

    def __init__(self, data={}, dyn_fields=[], fields=FieldHolder(), client=None):
        # if no client is specified, use the global client if possible
        if client is None:
            client = state.G_CLIENT

        # copy configuration from client if possible
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

        self._fields = FieldHolder()  # get an empty FH
        if self.client:
            self._fields += self.client.fields # fill it with the client fields
        self._fields.add(data)        # and anything passed in
        [self._fields.add_dynamic_field(fn) for fn in dyn_fields]
        self._fields += fields


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
        '''
        DEPRECATED - This will likely be removed in a future major version.

        Creates an event with the data passed in and enqueues it to be sent.
        Contrary to the name, it does not block the application when called.

        Shorthand for:

            ev = builder.new_event()
            ev.add(data)
            ev.send()
        '''
        ev = self.new_event()
        ev.add(data)
        ev.send()

    def new_event(self):
        '''creates a new event from this builder, inheriting all fields and
           dynamic fields present in the builder'''
        ev = Event(fields=self._fields, client=self.client)
        ev.writekey = self.writekey
        ev.dataset = self.dataset
        ev.api_host = self.api_host
        ev.sample_rate = self.sample_rate
        return ev

    def clone(self):
        '''creates a new builder from this one, creating its own scope to
           which additional fields and dynamic fields can be added.'''
        c = Builder(fields=self._fields, client=self.client)
        c.writekey = self.writekey
        c.dataset = self.dataset
        c.sample_rate = self.sample_rate
        c.api_host = self.api_host
        return c
