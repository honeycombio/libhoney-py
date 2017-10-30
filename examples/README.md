## Examples

- [Simple example](django_simple/my_app/honey_middleware.py) - captures basic metadata about each request coming through the django app
- [Response time example](django_response_time/my_app/honey_middleware.py) - captures response time as well as basic metadata for requests to the django app
- [Dynamic fields example](django_dynamic_fields/my_app/honey_middleware.py) - uses dynamic fields to generate values for the metric when `new_event()` is called, rather than the time of definition

## Installation

To build the examples:

1. `virtualenv examples_env`
2. `source examples_env/bin/activate`
3. `pip install -r ./requirements.txt`
4. `(cd ../ &&  python setup.py install) # this installs libhoney`

And then on each example:

5. `cd $example-dir`
6. `python manage.py migrate # initialize the project`
7. `HONEY_WRITE_KEY=YOUR_WRITE_KEY HONEY_DATASET=YOUR_DATASET python manage.py runserver`
