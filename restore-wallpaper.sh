#!/usr/bin/env bash
set -eu
BOB_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /usr/bin/python3 "$BOB_DIR/install_kde.py" restore
