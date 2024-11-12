#!/bin/sh
set -e

if [ ! -d .venv ]; then
    uv venv
fi
. .venv/bin/activate

uv pip install --upgrade syftbox

echo "Running '$pwd' with $(python3 --version) at '$(which python3)'"
python3 run.py --config=/Users/madhavajay/dev/syft/.clients/c@openmined.org/config.json
deactivate
