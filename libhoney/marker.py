import datetime
import random
from contextlib import contextmanager

from libhoney import state
from libhoney.fields import FieldHolder

_validations = {
    'start_time': int,
    'end_time': int,
    'message': str,
    'type': str,
    'url': str
}

class MarkerException(Exception):
    pass

class MarkerFieldsInvalidException(MarkerException):
    pass


class Marker(object):
    '''A demarcation of a point in time with associated metadata.'''
    def __init__(self, data={}, client=None):
        if client is None:
            self.client = state.G_CLIENT

        if self.client:
            self.writekey = self.client.writekey
            self.dataset = self.client.dataset
            self.api_host = self.client.api_host
            self.sample_rate = self.client.sample_rate
        else:
            self.writekey = None
            self.dataset = None
            self.api_host = 'https://api.honeycomb.io'
            self.sample_rate = 1

        # populate the event's fields
        self._fields = FieldHolder()  # get an empty FH
        self._fields.add(data)        # and anything passed ins

        # fill in other info
        self.created_at = datetime.datetime.utcnow()


    def fields(self):
        return self._fields._data

    def add(self, data: dict):
        for k, v in data.items():
            if k not in _validations:
                raise MarkerFieldsInvalidException(f"Invalid field: {k}")
            if not isinstance(v, _validations[k]):
                raise MarkerFieldsInvalidException(f"Invalid type for field {k}: {type(v)}")
        self._fields.add(data)
