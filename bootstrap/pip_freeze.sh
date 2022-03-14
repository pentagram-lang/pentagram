#!/bin/bash
set -e
EXCEPT=pyflakes
pip freeze --all \
    | cut -d = -f 1 \
    | grep -v "$EXCEPT" \
    | pip install -U -r /dev/stdin
pip check
pip freeze --all \
    > requirements.txt
