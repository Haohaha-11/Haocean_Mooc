SHELL := /usr/bin/env bash

.PHONY: test-a test-b test-c test smoke smoke-b verify clean-runtime

test-a:
	cd module_a_client && python3 -B -m unittest discover -s tests

test-b:
	cd module_b_server && .venv/bin/python -B -m unittest discover -s tests

test-c:
	cd module_c_controller && .venv/bin/python -m pytest -q

test: test-a test-b test-c

smoke-b:
	cd module_b_server && bash scripts/smoke_test.sh

smoke: smoke-b

verify:
	bash module_d_ops/scripts/verify_all.sh

clean-runtime:
	find module_a_client module_b_server module_c_controller -type d -name __pycache__ -prune -exec rm -rf {} +
