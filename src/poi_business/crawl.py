"""crawl.py - 北京 POI 多边形网格抓取（限速 + 断点续传）

用法:
  uv run python -m poi_business.crawl                      # 默认 city + 全部商业大类
  uv run python -m poi_business.crawl --roi beijing        # 全市域
  uv run python -m poi_business.crawl --types 05,06        # 只抓餐饮+购物
  uv run python -m poi_business.crawl --limit-grids 2      # 小范围试跑

断点续传:
  - 原始响应分页落盘 data/raw/chunks/poi_<type>_<grid>_p<page>.json
  - 进度 data/raw/progress.json（已完成网格+类型跳过）
  - 失败记录 data/raw/failures.jsonl（配额用尽后重跑续传）

API Key 从 .env 读取（AMAP_KEY），不入库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from poi_business.amap_client import AmapClient, AmapError, RateLimitedError
from poi_business.roi import COMMERCE_TYPES, ROIS, Grid, make_grids

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw"
CHUNK_DIR = DATA_DIR / "chunks"
PROGRESS_FILE = DATA_DIR / "progress.json"
FAILURES_FILE = DATA_DIR / "failures.jsonl"


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _record_failure(rec: dict) -> None:
    with open(FAILURES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _max_done_page(grid_id: str, typecode: str) -> int:
    """该 (网格,类型) 已落盘的最后一页；没有则 0。"""
    pages = [
        int(p.stem.rsplit("_p", 1)[1])
        for p in CHUNK_DIR.glob(f"poi_{typecode}_{grid_id}_p*.json")
    ]
    return max(pages, default=0)


def _fetch_grid_type(
    client: AmapClient,
    grid: Grid,
    typecode: str,
) -> tuple[int, int]:
    """抓取单网格+单类型全量分页。返回 (完成页数, 总条数)。

    断点：从已落盘页 +1 继续；配额用尽抛 RateLimitedError。
    """
    start_page = _max_done_page(grid.id, typecode) + 1
    total: int | None = None
    done = start_page - 1
    page = start_page

    while True:
        data = client.fetch_polygon(grid.polygon, typecode, page=page)
        if total is None:
            total = int(data.get("count", 0))
        pois = data.get("pois") or []

        out = CHUNK_DIR / f"poi_{typecode}_{grid.id}_p{page}.json"
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        done = page

        if not pois:
            break
        if page * 25 >= (total or 0):
            break
        page += 1
    return done, (total or 0)


def crawl(
    key: str,
    roi_name: str,
    type_codes: list[str],
    step: float,
    limit_grids: int | None,
) -> int:
    bbox = ROIS[roi_name]
    grids = make_grids(bbox, step)
    if limit_grids:
        grids = grids[:limit_grids]
    type_codes = type_codes or list(COMMERCE_TYPES)

    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    client = AmapClient(key)
    progress = _load_progress()

    print(f"[START] roi={roi_name} grids={len(grids)} types={len(type_codes)} step={step}")
    for grid in tqdm(grids, desc="grids"):
        for code in type_codes:
            key_id = f"{grid.id}_{code}"
            if progress.get(key_id, {}).get("complete"):
                continue
            try:
                done, total = _fetch_grid_type(client, grid, code)
                progress[key_id] = {"complete": True, "pages": done, "count": total}
                print(f"  [OK] {key_id} pages={done} count={total}")
            except RateLimitedError as e:
                print(f"[QUOTA] {key_id} -> {e}")
                _save_progress(progress)
                print("[END] 配额用尽，已保存进度，稍后重跑即可续传。")
                return 1
            except AmapError as e:
                _record_failure({"grid": grid.id, "type": code, "error": str(e)})
                print(f"[FAIL] {key_id} -> {e}")
            _save_progress(progress)

    n_chunks = len(list(CHUNK_DIR.glob("*.json")))
    print(f"[END] chunks={n_chunks} api_calls={client.calls} 完成。下一步: uv run python -m poi_business.merge")
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("AMAP_KEY", "").strip()
    if not key:
        print("[ERROR] 未找到 AMAP_KEY，请检查 .env")
        return 2

    parser = argparse.ArgumentParser(description="高德 POI 网格抓取")
    parser.add_argument("--roi", choices=sorted(ROIS), default="city", help="研究区域")
    parser.add_argument("--types", default="", help="类型代码逗号分隔，如 05,06；默认全部商业大类")
    parser.add_argument("--step", type=float, default=0.05, help="网格边长(度)")
    parser.add_argument("--limit-grids", type=int, default=None, help="只抓前 N 个网格(试跑)")
    args = parser.parse_args()

    type_codes = [t.strip() for t in args.types.split(",") if t.strip()]
    return crawl(
        key=key,
        roi_name=args.roi,
        type_codes=type_codes,
        step=args.step,
        limit_grids=args.limit_grids,
    )


if __name__ == "__main__":
    sys.exit(main())
