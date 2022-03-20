#!/bin/bash
set -e
pip install -c requirements.txt pip
pip install -r requirements.txt -e .
