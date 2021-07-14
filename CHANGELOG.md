# libhoney Changelog

## 1.11.0 2021-07-14

Improvements

- Make transmission queue sizes configurable (#69)

## Maintenance 

- Updates Github Action Workflows (#68)
- Adds dependabot (#67)
- Switches CODEOWNERS to telemetry-team (#66)
- add our custom action to manage project labels (#64)
- Use public CircleCI context for build secrets (#63)

## 1.10.0 2020-09-24

Improvements

- Schedule nightly builds on CirleCI (#57)
- Add .editorconfig to help provide consistent IDE styling (#59)

## 1.9.1 2020-07-23

Improvements

- Now using [poetry](https://python-poetry.org/) for packaging and dependency management.
- Updated to use current CircleCI badge instead of outdated TravisCI badge

## 1.9.0 2019-08-28

Features

- The default Transmission implementation now supports a `proxies` argument, which accepts a map defining http/https proxies. See the [requests](https://2.python-requests.org/en/master/user/advanced/#proxies) docs on proxies for more information.

## 1.8.0 2019-7-16 - Update recommended

Improvements

- Default Transmission implementation now compresses payloads by default (using gzip compression level 1). Compression offers significant savings in network egress at the cost of some CPU. Can be disabled by overriding `transmission_impl` when calling `libhoney.init()` and specifying `gzip_enabled=False`. See our official [docs](https://docs.honeycomb.io/getting-data-in/python/sdk/#customizing-event-transmission) for more information about overriding the default transmission.

## 1.7.2 2019-7-11

Fixes

- Switches default `send_frequency` type in the Tornado transmission implementation from float to timedelta, the correct type to use when fetching from tornado queues. Use of the float resulted in higher than expected CPU utilization. See [#49](https://github.com/honeycombio/libhoney-py/pull/49) for more details.

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

## 1.5.0 2018-08-29

Features

- Adds new, optional `FileTransmission` transmission type for outputing to a file. Defaults to stdout. [#38](https://github.com/honeycombio/libhoney-py/pull/38)

## 1.4.0 2018-07-12

Features

- Adds new `flush` method to instantly send all pending events to Honeycomb. [#37](https://github.com/honeycombio/libhoney-py/pull/37)

## 1.3.3 2018-06-26

Fixes

- Fixes a positional/keyword argument mixup in the `Client` class. [#36](https://github.com/honeycombio/libhoney-py/pull/37)

## 1.3.2 2018-06-22

Fixes

- `Client` class now supports `user_agent_addition` argument. [#35](https://github.com/honeycombio/libhoney-py/pull/35)

## 1.3.0 2018-06-19

Features

- Adds `Client` class. Previously, the libhoney library operated arounda single global state. This state is now packaged in the `Client` class, enabling multiple simultaneous configurations. The global state is now backed by a default `Client` instance.

## 1.2.3 2018-06-01

Features

- Adds a `Transmission` implementation for Tornado.

## 1.2.2 2018-04-23

Fixes

- Support older versions of requests package.

## 1.2.1 2018-03-27 Update Recommended

Fixes

- Batch payloads were not passing timestamp information to the API correctly.

## 1.2.0 2018-03-08

Improvements

- Libhoney now transmits multiple events using the batch API. Previously, each event was sent as a separate request to the events API.
