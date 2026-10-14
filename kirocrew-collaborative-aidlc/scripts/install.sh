#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$ROOT/scripts/validate_bundle.py"
kirocrew app install "$ROOT"
kirocrew app enable collaborative-aidlc-kirocrew
kirocrew doctor
