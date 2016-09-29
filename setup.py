from setuptools import setup

setup(name='libhoney',
      version='1.0.0',
      description='Python library for sending data to Honeycomb',
      url='https://github.com/honeycombio/libhoney-py',
      author='Honeycomb.io',
      author_email='feedback@honeycomb.io',
      license='Apache',
      packages=['libhoney'],
      install_requires=[
          'requests',
          'transmission',
          'statsd',
          'six',
      ],
      zip_safe=False)
