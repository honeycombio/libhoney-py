# libhoney Changelog

## 1.7.1 2019-03-29

Documentation updates only.

## 1.7.0 2019-02-10 - Update recommended

Improvements

- JSON encoder now defaults to string encoding of types not handled by the default encoder (such as datetime). Previously, these would result in a `TypeError` being raised during event serialization, causing the event to be dropped.

Security Updates

- Updates example Django app to 1.8.19 in response to [CVE-2017-7233](https://nvd.nist.gov/vuln/detail/CVE-2017-7233).

## 1.6.2 2018-10-09

Improvements

- Adds default HTTP timeout of 10s. Previously, connections to the Honeycomb API would never timeout, blocking sending threads forever if communication or API service was disrupted.

## 1.6.1 2018-10-01

Fixes

- Prevents rare RuntimeError leak during shutdown.

## 1.6.0 2018-09-21

Features

- Adds debug mode for verbose logging of libhoney activities to stderr. This can be enabled by passing `debug=True` to `init`.

Improvements

- Improperly configured events now log an error rather than raise a `SendError` exception.

Deprecations

- `send_now` is deprecated, you should use `new_event` to create a new event combined with `Event.send()` to enqueue the event. `send_now` does not block the application to send events immediately, but its name had generated significant confusion.
