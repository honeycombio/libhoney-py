## Examples

- [Django simple example](django_simple/my_app/honey_middleware.py) - captures basic metadata about each request coming through the django app
- [Django response time example](django_response_time/my_app/honey_middleware.py) - captures response time as well as basic metadata for requests to the django app
- [Django dynamic fields example](django_dynamic_fields/my_app/honey_middleware.py) - uses dynamic fields to generate values for the metric when `new_event()` is called, rather than the time of definition

- [Factorial](factorial/example.py) - examples of how to use some of the features of libhoney in python, a single file that uses a factorial to generate events
- [Tornado Factorial](factorial/example_tornado.py) - examples of how to use some of the features of libhoney in python, a single file that uses a factorial to generate events and sends them with Tornado async http client

## Installation

Inside each example django directory:

1. `poetry install`
2. `poetry run python manage.py migrate # initialize the project`
3. `HONEYCOMB_API_KEY=api-key HONEYCOMB_DATASET=django-example poetry run python manage.py runserver`
   
For the Factorial examples, there's no need to run the migrate step. Do only this:
1. `poetry install`
2. `HONEYCOMB_API_KEY=api-key poetry run python3 example_tornado.py` or `example.py`
