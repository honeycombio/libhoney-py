import inspect
import json

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
