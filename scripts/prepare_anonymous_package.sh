#!/bin/bash
# Build the two anonymous archives for the ARR/NAACL supplementary upload:
#   $2/suffice-code.zip   this repository without .git
#   $2/suffice-data.zip   the dataset directory ($1)
# then scan both for identifying strings; fail if any survive.
#   scripts/prepare_anonymous_package.sh dist/suffice-dataset dist/anonymous
set -euo pipefail
DATASET_DIR=${1:?dataset directory}
OUT=${2:?output directory}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$OUT"
rm -f "$OUT/suffice-code.zip" "$OUT/suffice-data.zip"
( cd "$ROOT" && zip -qr "$OUT/suffice-code.zip" . -x '.git/*' '*/__pycache__/*' '*.pyc' '.pytest_cache/*' 'dist/*' 'bench/*' '.env' )
( cd "$(dirname "$DATASET_DIR")" && zip -qr "$OUT/suffice-data.zip" "$(basename "$DATASET_DIR")" -x '*/__pycache__/*' '*.pyc' )
python3 "$ROOT/scripts/check_anonymity.py" "$OUT/suffice-code.zip" "$OUT/suffice-data.zip" ${ANONYMITY_PRIVATE_PATTERNS:+--private-patterns "$ANONYMITY_PRIVATE_PATTERNS"}
ls -la "$OUT"
