#!/bin/bash
set -e
pip-compile --quiet --allow-unsafe --generate-hashes --build-isolation --output-file requirements.txt requirements.in
pip-sync
pip install -e .
pip check
