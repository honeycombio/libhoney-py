# Local Development

## Requirements

Python: https://www.python.org/downloads/

Poetry: https://python-poetry.org/docs/#installation

## Install Dependencies

```shell
poetry install
```

## Run Tests

To run all tests:

```shell
poetry run coverage run -m unittest discover -v
```

To run individual tests:

```shell
poetry run coverage run -m unittest libhoney/test_transmission.py
```
