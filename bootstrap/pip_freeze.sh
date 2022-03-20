#!/bin/bash
set -e
pip check
pip freeze --all \
    | grep -v '^-e ' \
    > requirements.txt
pip-compile --allow-unsafe --generate-hashes --build-isolation
