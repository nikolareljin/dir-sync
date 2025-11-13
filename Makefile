.PHONY: lint test build run

lint:
	scripts/lint.sh

test:
	scripts/run_tests.sh

build:
	scripts/build.sh

run:
	python -m dirsync.app
