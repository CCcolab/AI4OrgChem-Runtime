#!/bin/sh
set -eu
cd /opt/runtime
exec python -m runtime.cli "$@"
