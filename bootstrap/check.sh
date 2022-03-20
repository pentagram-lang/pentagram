#!/bin/bash
set -e
pytest .
isort .
black .
flake8 .
mypy .
