A Python library for sending data to Honeycomb (http://honeycomb.io)
========================================================

## Summary

libhoney is written to ease the process of sending data to Honeycomb from within
your python code.

For an overview of how to use a honeycomb library, see our documentation at
https://honeycomb.io/docs/send-data/sdks/

For specifics on the python libhoney, check out the
[pydoc](https://honeycomb.io/docs/send-data/sdks/python/)

## Basic usage:

* call `init` to initialize libhoney with your Honeycomb writekey and dataset
  name
* create an event object and populate it with fields
* send the event object
* call `close` when your program is finished

## Example

```
# call init before using libhoney
libhoney.init(writekey="abcd1234", dataset="my data")
# create an event and add fields to it
ev = Event()
ev.add_field("duration_ms", 153.12)
ev.add_field("method", "get")
# send the event
ev.send()

# when all done, call close
libhoney.close()
```

You can find a more complete example demonstrating usage in `example.py`

## Contributions

Features, bug fixes and other changes to libhoney are gladly accepted. Please
open issues or a pull request with your change. Remember to add your name to the
CONTRIBUTORS file!

All contributions will be released under the Apache License 2.0.
