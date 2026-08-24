"""analysis.py - 商业空间结构全流程分析

集成所有分析步骤的 CLI 入口。

Step 2: 核密度估计 (KDE)
Step 2.5: 平均最近邻 (ANN)
Step 2.7: Ripley's K 多尺度集聚
Step 3: 全局/局部 Moran's I
Step 4: DBSCAN 商圈聚类
Step 5: 等级体系专题图

用法:
  uv run python -m poi_business.analysis            # 运行全部步骤
  uv run python -m poi_business.analysis --step 2   # 只运行 KDE
  uv run python -m poi_business.analysis --step 3   # 只运行 Moran
  uv run python -m poi_business.analysis --step 4   # 只运行 DBSCAN
  uv run python -m poi_business.analysis --step 5   # 只运行地图可视化
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis_modules import step2_5_ann, step2_7_ripley, step2_kde, step3_moran, step4_dbscan, step5_map
from .analysis_modules.utils import OUT_DIR, load_data, make_grid
from .logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> int:
    """主程序：加载数据，选择性运行分析步骤。"""
    setup_logging()
    parser = argparse.ArgumentParser(
        description="北京商业空间结构分析工具",
        epilog="更多信息请查看 README.md",
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[2, 25, 27, 3, 4, 5],
        help="步骤 (2=KDE, 25=ANN, 27=RipleyK, 3=Moran, 4=DBSCAN, 5=地图)，默认全部",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("北京商业空间结构分析 - 全流程分析工具")
    logger.info("=" * 60)

    try:
        df = load_data()
        logger.info("加载 %d 条 POI (7 大类)", len(df))
        df = make_grid(df)
        logger.info("网格化完成 (%d 格网)", len(df.groupby(["gx", "gy"])))
    except FileNotFoundError as e:
        logger.error("数据文件未找到: %s，请先运行数据采集和合并流程", e)
        return 1
    except Exception as e:
        logger.error("数据加载失败: %s", e)
        return 1

    steps = [args.step] if args.step else [2, 25, 27, 3, 4, 5]
    logger.info("执行步骤: %s", steps)

    step_funcs = {
        2: step2_kde, 25: step2_5_ann, 27: step2_7_ripley,
        3: step3_moran, 4: step4_dbscan, 5: step5_map,
    }
    for step in steps:
        try:
            step_funcs[step](df)
        except Exception as e:
            logger.error("步骤 %d 执行失败: %s", step, e)
            return 1

    logger.info("=" * 60)
    logger.info("分析完成！输出文件:")
    logger.info("=" * 60)
    for f in sorted(OUT_DIR.glob("*")):
        if f.suffix in (".csv", ".json", ".html", ".txt"):
            size_kb = f.stat().st_size / 1024
            logger.info("  %-40s %8.1f KB", f.name, size_kb)
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
