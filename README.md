# libhoney [![Build Status](https://travis-ci.org/honeycombio/libhoney-py.svg?branch=master)](https://travis-ci.org/honeycombio/libhoney-py)

Python library for sending events to [Honeycomb](https://honeycomb.io). (See here for more information about [using Honeycomb](https://honeycomb.io/intro/) and [its libraries](https://honeycomb.io/docs/send-data/sdks).)

## Installation

```
pip install libhoney
```

## Documentation

A pydoc API reference is available at https://honeycomb.io/docs/send-data/sdks/python/

## Example

Honeycomb can calculate all sorts of statistics, so send the values you care about and let us crunch the averages, percentiles, lower/upper bounds, cardinality -- whatever you want -- for you.

```python
import libhoney

# Call init to configure libhoney
libhoney.init(writekey="YOUR_WRITE_KEY", dataset="honeycomb-python-example")

libhoney.send_now({
  "duration_ms": 153.12,
  "method": "get",
  "hostname": "appserver15",
  "payload_length": 27
})

# Call close to flush any pending calls to Honeycomb
libhoney.close()
```

You can find a more complete example demonstrating usage in [`example.py`](example.py)

## Contributions

Features, bug fixes and other changes to libhoney are gladly accepted. Please
open issues or a pull request with your change. Remember to add your name to the
CONTRIBUTORS file!

All contributions will be released under the Apache License 2.0.

## Releases
To release a new version, run
```
bumpversion [major|minor|patch]
git push --tags
```
After a successful build, a new version will be automatically uploaded to PyPI.
