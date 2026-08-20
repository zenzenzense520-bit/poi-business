"""roi.py - 研究区域网格切分 + 商业 POI 大类定义

研究思路：把研究区域切成等经纬度网格，逐网格调用多边形搜索
（polygon），保证高德单页 25 条限制下也能全量取到。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Grid:
    index: int
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    @property
    def id(self) -> str:
        return f"g{self.index:04d}"

    @property
    def polygon(self) -> str:
        """多边形顶点串（左下→右下→右上→左上→闭合），供 polygon 搜索使用。"""
        return (
            f"{self.lon_min},{self.lat_min};"
            f"{self.lon_max},{self.lat_min};"
            f"{self.lon_max},{self.lat_max};"
            f"{self.lon_min},{self.lat_max};"
            f"{self.lon_min},{self.lat_min}"
        )


# 预设研究区域（WGS84 经纬度）
ROIS: dict[str, dict[str, float]] = {
    # 北京市域（含远郊区，用于全景）
    "beijing": {
        "lon_min": 115.42, "lon_max": 117.51,
        "lat_min": 39.43, "lat_max": 41.06,
    },
    # 中心六区（东城/西城/朝阳/海淀/丰台/石景山，POI 密集，推荐首跑）
    "city": {
        "lon_min": 116.00, "lon_max": 116.70,
        "lat_min": 39.75, "lat_max": 40.20,
    },
}

# 商业相关 POI 大类（高德两位类型代码）
COMMERCE_TYPES: dict[str, str] = {
    "05": "餐饮服务",
    "06": "购物服务",
    "08": "体育休闲服务",
    "09": "医疗保健服务",
    "10": "住宿服务",
    "16": "金融保险服务",
    "17": "公司企业",
}


def make_grids(bbox: dict[str, float], step: float = 0.05) -> list[Grid]:
    """把 bbox 按 step（度）切成网格列表。

    Args:
        bbox: {"lon_min","lon_max","lat_min","lat_max"}
        step: 网格边长（度）。0.05° ≈ 5.5km，POI 密集区可调小到 0.02°
    """
    grids: list[Grid] = []
    idx = 0
    x = bbox["lon_min"]
    while x < bbox["lon_max"] - 1e-9:
        y = bbox["lat_min"]
        while y < bbox["lat_max"] - 1e-9:
            x1 = min(x + step, bbox["lon_max"])
            y1 = min(y + step, bbox["lat_max"])
            grids.append(Grid(idx, x, x1, y, y1))
            idx += 1
            y = y1
        x = x1
    return grids
