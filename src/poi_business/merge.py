"""merge.py - 合并抓取 chunks 为统一数据集（按 id 去重）

用法:
  uv run python -m poi_business.merge

输出:
  - data/processed/beijing_poi.csv.gz   统一 POI 表（含 lon/lat）
  - data/processed/summary.json         数量与按大类统计
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CHUNK_DIR = ROOT / "data" / "raw" / "chunks"
OUT_DIR = ROOT / "data" / "processed"

# 高德 v3 place 返回字段子集
KEEP = [
    "id", "name", "type", "typecode", "address", "location",
    "tel", "pname", "cityname", "adname", "business_area",
]


def _iter_pois():
    for fp in sorted(CHUNK_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for poi in data.get("pois") or []:
            yield {k: poi.get(k) for k in KEEP}


def main() -> int:
    rows = list(_iter_pois())
    if not rows:
        print("[ERROR] 无数据，请先运行 crawl")
        return 1

    df = pd.DataFrame(rows)
    # location 形如 "116.40,39.90" -> lon/lat 两列
    split = df["location"].str.split(",", expand=True)
    df["lon"] = pd.to_numeric(split[0], errors="coerce")
    df["lat"] = pd.to_numeric(split[1], errors="coerce")
    df = df.drop_duplicates(subset="id", keep="first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "beijing_poi.csv.gz"
    df.to_csv(out_path, index=False, compression="gzip")

    summary = {
        "n_raw": len(rows),
        "n_unique": int(len(df)),
        "by_type": {k: int(v) for k, v in df["type"].str[:2].value_counts().items()},
        "file": str(out_path),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[DONE] POI 总数={len(df)} (去重前 {len(rows)}) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
