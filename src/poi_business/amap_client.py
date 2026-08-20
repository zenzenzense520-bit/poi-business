"""amap_client.py - 高德 Web 服务 API 客户端（限速 + 指数退避重试）

端点: https://restapi.amap.com/v3/place/polygon  多边形 POI 搜索

职责单一：
- 按 QPS 限速（同一 key 并发请求会触发风控，抓取保持串行）
- 网络层错误（HTTP!=200 / 超时 / JSON 解析失败）指数退避重试
- 配额/权限类业务错误立即抛出，不做无意义重试
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

import requests

BASE_URL = "https://restapi.amap.com/v3/place/polygon"

# 致命错误码：无需重试（Key 无效/参数错误/签名/IP 未授权等）
FATAL_CODES = {"10001", "10003", "10004", "10006", "10007"}
# 配额/并发限制错误码：等待后重跑（断点续传支持）
QUOTA_CODES = {"40001", "40002", "40003", "40004"}


class AmapError(RuntimeError):
    """请求最终失败（网络重试耗尽或参数类错误）"""


class RateLimitedError(AmapError):
    """每日配额用尽或并发超限，需稍后重跑"""


class AmapClient:
    """带限速与重试的高德客户端。"""

    def __init__(
        self,
        key: str,
        qps: float = 3.0,
        max_retries: int = 4,
        timeout: int = 20,
    ) -> None:
        self.key = key
        self.min_interval = 1.0 / max(0.5, qps)
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_call = 0.0
        self.calls = 0

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _backoff(self, attempt: int) -> None:
        time.sleep(min(2 ** attempt, 16) + random.uniform(0, 0.5))

    def fetch_polygon(
        self,
        polygon: str,
        types: str,
        page: int = 1,
        offset: int = 25,
    ) -> dict[str, Any]:
        """抓取单个多边形+类型的单页 POI，成功返回完整 JSON 响应。

        Args:
            polygon: 多边形顶点串 "lon,lat;lon,lat;..."
            types: 高德类型代码（大类为两位数字，如 "06"）
            page: 页码（从 1 起）
            offset: 每页条数（高德 v3 上限 25）
        """
        params = {
            "key": self.key,
            "polygon": polygon,
            "types": types,
            "page": page,
            "offset": offset,
            "extensions": "all",
        }
        last_err: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                resp = requests.get(BASE_URL, params=params, timeout=self.timeout)
                self.calls += 1
                if resp.status_code != 200:
                    raise requests.RequestException(f"HTTP {resp.status_code}")
                data = resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                last_err = e
                if attempt < self.max_retries:
                    self._backoff(attempt)
                continue

            status = data.get("status")
            if status == "1":
                return data

            infocode = str(data.get("infocode", ""))
            info = str(data.get("info", ""))
            if infocode in FATAL_CODES:
                raise AmapError(f"高德致命错误 code={infocode} info={info}")
            if infocode in QUOTA_CODES:
                raise RateLimitedError(f"配额/并发限制 code={infocode} info={info}")
            last_err = AmapError(f"高德业务错误 code={infocode} info={info}")
            if attempt < self.max_retries:
                self._backoff(attempt)

        raise AmapError(f"请求失败（重试{self.max_retries}次耗尽）: {last_err}")
