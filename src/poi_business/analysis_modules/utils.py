"""分析工具 - 数据加载和网格化

本模块提供数据加载、网格化等基础工具。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed" / "beijing_poi.csv.gz"
OUT_DIR = ROOT / "data" / "processed"

# 分析用 7 大类
CATEGORIES = {
    "05": "餐饮", "06": "购物", "08": "体育",
    "09": "医疗", "10": "住宿", "16": "金融", "17": "公司",
}

# 网格参数
GRID_STEP = 0.005  # ≈500m


def load_data() -> pd.DataFrame:
    """加载 POI 数据并过滤 7 大类。

    支持两种格式：
    - typecode 为字符串 ('050000') → 取前两位 '05'
    - type 为整数 (5) → 格式化为 '05'
    """
    df = pd.read_csv(DATA)
    if df["typecode"].dtype == object:
        df["cat"] = df["typecode"].str[:2]
    else:
        df["cat"] = df["type"].apply(lambda x: f"{int(x):02d}")
    df = df[df["cat"].isin(CATEGORIES)].copy()
    return df


def make_grid(df: pd.DataFrame, step: float = GRID_STEP) -> pd.DataFrame:
    """把 POI 点聚合到等经纬度格网。"""
    lon_min, lon_max = df["lon"].min(), df["lon"].max()
    lat_min, lat_max = df["lat"].min(), df["lat"].max()
    x = np.floor((df["lon"] - lon_min) / step).astype(int)
    y = np.floor((df["lat"] - lat_min) / step).astype(int)
    df = df.copy()
    df["gx"] = x
    df["gy"] = y
    df["gx_lon"] = lon_min + (x + 0.5) * step
    df["gy_lat"] = lat_min + (y + 0.5) * step
    return df
