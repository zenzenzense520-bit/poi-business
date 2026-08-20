# Beijing POI 商业空间结构分析

基于高德 POI 数据的北京市商业空间结构研究。

## 技术栈

Python 3.11 + uv · geopandas · PySAL(esda/splot/pointpats) · scikit-learn · folium/keplergl

## 数据采集

通过高德 Web 服务 API（`/v3/place/polygon`）按"研究区域网格 × POI 大类"全量抓取：

- 研究区域：`city`（中心六区）
- 网格边长：默认 0.05°（约 5.5km），可调小提高覆盖精度
- POI 大类：餐饮/购物/体育休闲/医疗/住宿/金融保险/公司企业

### 限速与断点续传

- 限速：QPS 默认 3.0，串行请求防风控
- 重试：网络错误指数退避（1/2/4/8s）
- 断点：原始响应分页落盘 `data/raw/chunks/`，进度 `progress.json`，
  已完成的 (网格, 类型) 重跑自动跳过；配额用尽后重跑即可续传
- API Key 存于 `.env`

## 使用

```bash
# 1. 配置 Key（.env）
AMAP_KEY=your_amap_key

# 2. 抓取（小范围试跑）
./scripts/run_crawl.sh --types 06 --limit-grids 2

# 3. 全量抓取（默认 city + 全部商业大类）
./scripts/run_crawl.sh

# 4. 合并去重 -> data/processed/beijing_poi.csv.gz
./scripts/run_merge.sh
```

## 目录结构

```
src/poi_business/
  amap_client.py   # 高德客户端：限速 + 指数退避重试
  roi.py           # 研究区域网格切分 + POI 大类定义
  crawl.py         # 主抓取：断点续传 + 失败记录
  merge.py         # chunks 合并去重为统一数据集
data/raw/          # 原始响应与进度（不入库）
data/processed/    # 合并后的分析数据集（不入库）
scripts/           # 启停脚本
```

## 下一步（分析）

核密度 / 平均最近邻 / Ripley's K / 莫兰指数 / DBSCAN 商圈识别 / 等级体系。
