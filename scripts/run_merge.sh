#!/usr/bin/env bash
# 合并抓取结果：chunks -> data/processed/beijing_poi.csv.gz
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m poi_business.merge
