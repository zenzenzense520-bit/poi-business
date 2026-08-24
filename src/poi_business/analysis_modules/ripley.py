"""Step 2.7: Ripley's K 多尺度空间集聚分析

分析商业设施在不同空间尺度下的集聚/离散特征。

输出:
  - data/processed/ripley_k_summary.json (全局 K 统计)
  - data/processed/ripley_k_by_category.json (各大类 K 统计)
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from .utils import CATEGORIES, OUT_DIR


def compute_ripley_k(
    coords: np.ndarray,
    n_support: int = 20,
    n_simulations: int = 999,
    max_radius: float | None = None,
) -> dict:
    """计算 Ripley's K 及 L 变换。

    K(t): 以任意点为圆心、t 为半径的圆内期望点数 / 面积密度
    L(t) = sqrt(K(t) / pi) - t
    L(t) > 0 → 聚集, L(t) ≈ 0 → 随机, L(t) < 0 → 离散

    Args:
        coords: (n, 2) 投影坐标（米）
        n_support: 距离间隔数
        n_simulations: 置换检验模拟次数
        max_radius: 最大观测半径（米），None 则自动

    Returns:
        dict: support_m, k_obs, k_exp, l_obs, l_exp, pvalues,
              peak_distance_m, peak_l_value
    """
    from pointpats import k as ripley_k, k_test

    n = len(coords)
    if n < 10:
        return {"n_points": n}

    # 自动最大半径: 研究区域等效圆半径的 1/3
    if max_radius is None:
        x_range = coords[:, 0].max() - coords[:, 0].min()
        y_range = coords[:, 1].max() - coords[:, 1].min()
        area = x_range * y_range
        max_radius = np.sqrt(area / np.pi) / 3.0

    # 执行 K 检验
    result = k_test(
        coords,
        support=n_support,
        n_simulations=n_simulations,
        keep_simulations=False,
    )

    support = result.support  # 坐标单位（度/米）
    k_obs = result.statistic
    pvalues = result.pvalue

    # 期望 K (CSR): K_exp(t) = pi * t^2
    k_exp = np.pi * support ** 2

    # L 变换: L(t) = sqrt(K(t) / pi) - t
    # 避免负值开方
    l_obs = np.sqrt(np.maximum(k_obs, 0) / np.pi) - support
    l_exp = np.sqrt(np.maximum(k_exp, 0) / np.pi) - support

    # 找到 L(t) 的峰值（最大集聚尺度）
    if len(l_obs) > 1:
        # 跳过 t=0
        idx_peak = np.argmax(l_obs[1:]) + 1
        peak_distance_m = float(support[idx_peak])
        peak_l_value = float(l_obs[idx_peak])
    else:
        peak_distance_m = 0.0
        peak_l_value = 0.0

    return {
        "n_points": n,
        "support_m": support.tolist(),
        "k_obs": k_obs.tolist(),
        "k_exp": k_exp.tolist(),
        "l_obs": l_obs.tolist(),
        "l_exp": l_exp.tolist(),
        "pvalues": pvalues.tolist(),
        "peak_distance_m": round(peak_distance_m, 1),
        "peak_l_value": round(peak_l_value, 4),
        "n_significant": int((pvalues < 0.05).sum()),
    }


def step2_7_ripley(df: pd.DataFrame) -> None:
    """执行 Ripley's K 多尺度集聚分析。"""
    from pyproj import Transformer

    print("[Step 2.7] Ripley's K 多尺度空间集聚分析")
    t0 = time.time()

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32650", always_xy=True)
    x, y = transformer.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    coords_all = np.column_stack([x, y])

    # 全量
    result_all = compute_ripley_k(coords_all, n_support=20, n_simulations=999)
    if "peak_distance_m" in result_all:
        print(f"  [全量] 峰值尺度={result_all['peak_distance_m']:.0f}m  "
              f"L_peak={result_all['peak_l_value']:.4f}  "
              f"显著距离段={result_all['n_significant']}/20")

    # 各大类
    results_cat = {}
    for code, name in CATEGORIES.items():
        sub = df[df["cat"] == code]
        if len(sub) < 10:
            print(f"  [SKIP] {name}: 仅 {len(sub)} 条")
            continue
        sub_x, sub_y = transformer.transform(sub["lon"].to_numpy(), sub["lat"].to_numpy())
        sub_coords = np.column_stack([sub_x, sub_y])
        r = compute_ripley_k(sub_coords, n_support=20, n_simulations=499)
        if "peak_distance_m" in r:
            results_cat[code] = r
            print(f"  [{name}] 峰值={r['peak_distance_m']:.0f}m  "
                  f"L_peak={r['peak_l_value']:.4f}  "
                  f"显著={r['n_significant']}/20")

    # 输出
    summary = {"overall": result_all, "by_category": results_cat}
    out = OUT_DIR / "ripley_k_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  耗时: {time.time()-t0:.1f}s -> {out.name}")
