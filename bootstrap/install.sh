#!/bin/bash
set -e
awk '/^pip==/{p=1;print;next}/^[^ ]/{p=0}p' requirements.txt > /tmp/requirements.txt
pip install --no-deps -r /tmp/requirements.txt
awk '/^(pip-tools|click|pep517|tomli|wheel)==/{p=1;print;next}/^[^ ]/{p=0}p' requirements.txt > /tmp/requirements.txt
pip install --no-deps -r /tmp/requirements.txt
pip-compile --allow-unsafe --generate-hashes --build-isolation --output-file /tmp/requirements.txt
pip install --no-deps -r requirements.txt
pip install -e .
