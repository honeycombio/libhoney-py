build:
	poetry build

clean:
	rm -rf libhoney/__pycache__/
	rm -rf dist/*

install:
	poetry install --no-root --no-ansi

lint:
	poetry run pylint --rcfile=pylint.rc libhoney

format:
	poetry run pycodestyle libhoney --max-line-length=140

test:
	poetry run coverage run -m unittest discover -v

smoke:
	@echo ""
	@echo "+++ Running example app in docker"
	@echo ""
	docker-compose up --build --exit-code-from factorial-example

unsmoke:
	@echo ""
	@echo "+++ Spinning down example app in docker"
	@echo ""
	docker-compose down

.PHONY: build clean install lint format test smoke unsmoke
