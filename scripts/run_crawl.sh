#!/usr/bin/env bash
# 抓取 POI：默认 city 区域 + 全部商业大类。
# 传参直接透传给 crawl，例如 ./scripts/run_crawl.sh --types 05,06 --limit-grids 2
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m poi_business.crawl "$@"
