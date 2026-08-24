"""Step 2.5: 平均最近邻 (ANN) 空间分布检验

判断 POI 点 pattern 是聚集、随机还是均匀。

输出:
  - data/processed/ann_summary.json (全局 ANN 统计)
  - data/processed/ann_by_category.json (各大类 ANN)
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .utils import CATEGORIES, OUT_DIR


def compute_ann(coords: np.ndarray, n_perm: int = 999) -> dict:
    """计算平均最近邻指数及置换检验 Z 值。

    ANN = 观测平均 NN 距离 / 期望平均 NN 距离
    ANN < 1 → 聚集, ANN ≈ 1 → 随机, ANN > 1 → 均匀

    Args:
        coords: (n, 2) 坐标数组 (投影坐标，单位: 米)
        n_perm: 置换检验次数

    Returns:
        dict: ann_ratio, observed_mean, expected_mean, z_score, p_value
    """
    n = len(coords)
    if n < 3:
        return {"ann_ratio": np.nan, "n_points": n, "p_value": np.nan}

    # 构建 KD 树，查询最近邻（k=2 包含自身）
    tree = cKDTree(coords)
    dists, _ = tree.query(coords, k=2)
    nn_dists = dists[:, 1]  # 第二近 = 真正的最近邻

    observed_mean = float(nn_dists.mean())

    # 期望值 (CSR 假设下): E[d] = 0.5 * sqrt(A / n)
    # 用凸包面积更准确；退而求其次用 bounding box
    x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
    y_min, y_max = coords[:, 1].min(), coords[:, 1].max()
    area = (x_max - x_min) * (y_max - y_min)
    expected_mean = 0.5 * np.sqrt(area / n)

    ann_ratio = observed_mean / expected_mean if expected_mean > 0 else np.nan

    # 置换检验：随机打乱坐标，计算 ANN 分布
    if n_perm > 0 and area > 0:
        rng = np.random.default_rng(42)
        perm_means = np.empty(n_perm)
        for i in range(n_perm):
            rand_coords = np.column_stack([
                rng.uniform(x_min, x_max, n),
                rng.uniform(y_min, y_max, n),
            ])
            rand_tree = cKDTree(rand_coords)
            rand_dists, _ = rand_tree.query(rand_coords, k=2)
            perm_means[i] = rand_dists[:, 1].mean()

        # Z = (观测 - 均值) / 标准差
        z_score = (observed_mean - perm_means.mean()) / (perm_means.std() + 1e-30)
        # p: 双尾检验（观测值在置换分布中的极端程度）
        p_value = float(np.mean(np.abs(perm_means - perm_means.mean()) >=
                                np.abs(observed_mean - perm_means.mean())))
    else:
        z_score = np.nan
        p_value = np.nan

    return {
        "n_points": n,
        "observed_mean_m": round(observed_mean, 2),
        "expected_mean_m": round(expected_mean, 2),
        "ann_ratio": round(ann_ratio, 4),
        "z_score": round(z_score, 3),
        "p_value": round(p_value, 4),
        "area_m2": round(area, 0),
    }


def step2_5_ann(df: pd.DataFrame) -> None:
    """执行平均最近邻分析。"""
    from pyproj import Transformer

    print("[Step 2.5] 平均最近邻 (ANN) 空间分布检验")
    t0 = time.time()

    # 投影到米制坐标
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32650", always_xy=True)
    x, y = transformer.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    coords_all = np.column_stack([x, y])

    # 全量 ANN
    result_all = compute_ann(coords_all, n_perm=999)
    print(f"  [全量] ANN={result_all['ann_ratio']:.4f}  "
          f"z={result_all['z_score']:.3f}  p={result_all['p_value']:.4f}  "
          f"{'聚集' if result_all['ann_ratio'] < 1 else '随机/均匀'}")

    # 各大类 ANN
    results_cat = {}
    for code, name in CATEGORIES.items():
        sub = df[df["cat"] == code]
        if len(sub) < 10:
            print(f"  [SKIP] {name}: 仅 {len(sub)} 条")
            continue
        sub_x, sub_y = transformer.transform(sub["lon"].to_numpy(), sub["lat"].to_numpy())
        sub_coords = np.column_stack([sub_x, sub_y])
        r = compute_ann(sub_coords, n_perm=499)
        results_cat[code] = r
        print(f"  [{name}] ANN={r['ann_ratio']:.4f}  z={r['z_score']:.3f}  p={r['p_value']:.4f}")

    # 输出
    summary = {"overall": result_all, "by_category": results_cat}
    out = OUT_DIR / "ann_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  耗时: {time.time()-t0:.1f}s -> {out.name}")
