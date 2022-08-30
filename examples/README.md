## Examples

- [Simple example](django_simple/my_app/honey_middleware.py) - captures basic metadata about each request coming through the django app
- [Response time example](django_response_time/my_app/honey_middleware.py) - captures response time as well as basic metadata for requests to the django app
- [Dynamic fields example](django_dynamic_fields/my_app/honey_middleware.py) - uses dynamic fields to generate values for the metric when `new_event()` is called, rather than the time of definition
- [Tornado](tornado/example_tornado.py) - uses Tornado ASYNC http client to send events

## Installation

Inside each example directory:

1. `poetry install`
2. `poetry run python manage.py migrate # initialize the project`
3. `HONEYCOMB_API_KEY=api-key HONEYCOMB_DATASET=django-example poetry run python manage.py runserver`
   
For Tornado example, there's no need to run the migrate step. Do only this:
1. `poetry install`
2. `HONEYCOMB_API_KEY=api-key poetry run python3 example_tornado.py`
