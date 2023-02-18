lint:
	isort src
	pylint src
	black src
	flake8 src

test:
	pytest src/tests --verbose --failed-first --cov=src --cov-report=html
