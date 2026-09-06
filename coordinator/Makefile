.PHONY: check
check:
	-python -m pytest coordinator/tests/ -v
	ruff format --check coordinator/
	ruff check coordinator/
	mypy coordinator/app/
