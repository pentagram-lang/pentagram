#!/bin/bash
set -e
pip freeze --all \
    | cut -d = -f 1 \
    | pip install -U -r /dev/stdin
pip check
pip freeze --all \
    > requirements.txt
