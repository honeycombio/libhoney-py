To upload a new release to PyPI:

1. Get the honeycomb PyPI password from lastpass.

2. Create a `.pypirc` file *in your home directory* with the following contents:
```
[distutils]
index-servers =
  pypi

[pypi]
repository=https://pypi.python.org/pypi
username=honeycomb
password=<password>
```

3. Make sure to bump the version in `libhoney/version.py`.

4. Run the tests: `python setup.py test`

4. `python setup.py sdist upload`
