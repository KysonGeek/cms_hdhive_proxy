"""
Python 代理服务 - 将原有接口请求转换为 HDHive API 调用
端口: 8900
"""

import os
import re
import logging
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ============================================================
# 加载 .env 配置
# ============================================================
load_dotenv()

HDHIVE_BASE = "https://hdhive.com/api/open"
HDHIVE_TOKEN = os.getenv("HDHIVE_TOKEN", "")
print(f'token: {HDHIVE_TOKEN}')

# 原始后端转存接口（通过 localhost 调用，跳过 Caddy 域名拦截）
LOCAL_SAVE_URL = "http://localhost:9527/api/cloud/add_share_down"

# HDHive 请求头（按需补充 Cookie / Authorization）
HDHIVE_HEADERS = {
    "Content-Type": "application/json",
}
if HDHIVE_TOKEN:
    HDHIVE_HEADERS["X-API-Key"] = HDHIVE_TOKEN

# ============================================================
# 初始化
# ============================================================
app = FastAPI(title="Movie Proxy Service")
logger = logging.getLogger("proxy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 媒体类型映射：HDHive 用 tv / movie 区分，但原接口统一用 movie
# 这里默认使用 movie，如果查不到再 fallback 到 tv
MEDIA_TYPES = ["movie", "tv"]


# ============================================================
# 工具函数
# ============================================================
async def hdhive_search(tmdbid: int) -> dict | None:
    """
    在 HDHive 上搜索资源，先尝试 movie，再尝试 tv
    返回原始 JSON 或 None
    """
    async with httpx.AsyncClient(timeout=30, headers=HDHIVE_HEADERS) as client:
        for media_type in MEDIA_TYPES:
            url = f"{HDHIVE_BASE}/resources/{media_type}/{tmdbid}"
            logger.info(f"HDHive search: {url}")
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("success") and body.get("data"):
                        return body
            except Exception as e:
                logger.warning(f"HDHive request failed ({media_type}): {e}")
    return None


def resolution_mapping(video_resolution: list[str] | None) -> str:
    """
    将 HDHive 的 video_resolution 列表转换为简单的分辨率字符串
    例如 ["4K"] -> "2160p", ["1080p"] -> "1080p"
    """
    if not video_resolution:
        return "unknown"
    res = video_resolution[0].upper()
    mapping = {
        "4K": "2160p",
        "2160P": "2160p",
        "1080P": "1080p",
        "720P": "720p",
    }
    return mapping.get(res, res)


def build_quality(item: dict) -> str | None:
    """
    从 source / subtitle_type 等信息中提取 quality 标签
    """
    parts = []
    sources = item.get("source") or []
    subtitle_types = item.get("subtitle_type") or []
    if sources:
        parts.extend(sources)
    if subtitle_types:
        parts.extend(subtitle_types)
    return ", ".join(parts) if parts else None


# ============================================================
# 接口1: 查询影片资源信息
# GET /api/nullbr/movie/{tmdbid}/resources
# ============================================================
@app.get("/api/nullbr/movie/{tmdbid}/resources")
async def movie_resources(tmdbid: int):
    result = await hdhive_search(tmdbid)
    if not result or not result.get("data"):
        return JSONResponse(
            content={"code": 200, "data": None},
            status_code=200,
        )

    items = result["data"]
    first = items[0]

    # 构建与原接口一致的返回格式
    response_data = {
        "code": 200,
        "data": {
            "movie_info": {
                "id": tmdbid,
                "title": first.get("title", ""),
                "poster": "",  # HDHive 不提供海报，留空
                "overview": "",  # HDHive 不提供简介，留空
                "vote": 0,
                "release_date": "",
            },
            "available_resources": {
                "has_115": any(i.get("pan_type") == "115" for i in items),
                "has_magnet": False,
                "has_ed2k": False,
                "has_video": False,
            },
        },
    }
    return JSONResponse(content=response_data)


# ============================================================
# 接口2: 获取115链接列表
# GET /api/nullbr/movie/{tmdbid}/115
# ============================================================
@app.get("/api/nullbr/movie/{tmdbid}/115")
async def movie_115_list(tmdbid: int, page: int = 1):
    result = await hdhive_search(tmdbid)
    if not result or not result.get("data"):
        return JSONResponse(
            content={
                "code": 200,
                "data": {
                    "tmdbid": tmdbid,
                    "page": 1,
                    "total_page": 0,
                    "resources": [],
                },
            }
        )

    items = result["data"]
    meta = result.get("meta", {})
    total = meta.get("total", len(items))

    # 只保留 pan_type == "115" 的资源
    items_115 = [i for i in items if i.get("pan_type") == "115"]

    # 简易分页（HDHive 单次返回全量，这里做客户端分页）
    page_size = 20
    total_page = max(1, (len(items_115) + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items_115[start:end]

    resources = []
    for item in page_items:
        if item.get("pan_type", "") != "115":
            continue;

        resources.append({
            "title": item.get("title", "") + " " + (
                "积分:免费" if not item.get("unlock_points") else f"积分:{item['unlock_points']}"
            ),
            "size": item.get("share_size", ""),
            # ★ 关键: share_link 放 slug，前端调用转存时会带上这个值
            "share_link": item.get("slug", ""),
            "resolution": resolution_mapping(item.get("video_resolution")),
            "quality": build_quality(item),
            "season_list": None,
            # 额外信息（方便前端展示）
            "remark": item.get("remark", ""),
            "unlock_points": item.get("unlock_points", 0),
            "is_unlocked": item.get("is_unlocked", False),
        })

    return JSONResponse(
        content={
            "code": 200,
            "data": {
                "tmdbid": tmdbid,
                "page": page,
                "total_page": total_page,
                "resources": resources,
            },
        }
    )


# ============================================================
# 接口3: 转存
# POST /api/cloud/add_share_down
# 原请求体: {"url": "https://115cdn.com/s/xxx?password=yyy&#"}
# 现在 url 字段实际传的是 HDHive 的 slug
# 流程: unlock(slug) -> 拿到真实115链接 -> 调用原始转存接口
# ============================================================
@app.post("/api/cloud/add_share_down")
async def cloud_add_share_down(request: Request):
    body = await request.json()
    raw_url = body.get("url", "")

    # 判断传入的是 slug 还是原始115链接
    # slug 格式: 32位hex，例如 c68ce9afa88b11ef87c60242ac120005
    is_slug = bool(re.match(r"^[a-f0-9]{32}$", raw_url))

    if is_slug:
        # ---- 新流程: HDHive unlock -> 获取真实链接 -> 转存 ----
        slug = raw_url
        logger.info(f"Unlock slug: {slug}")

        # Step 1: 调用 HDHive unlock 接口
        async with httpx.AsyncClient(timeout=30, headers=HDHIVE_HEADERS) as client:
            try:
                unlock_resp = await client.post(
                    f"{HDHIVE_BASE}/resources/unlock",
                    json={"slug": slug},
                )
                unlock_data = unlock_resp.json()
                logger.info(f"Unlock response: {unlock_data}")
            except Exception as e:
                logger.error(f"Unlock failed: {e}")
                return JSONResponse(
                    content={"code": 500, "message": f"HDHive unlock failed: {e}"},
                    status_code=500,
                )

        if not unlock_data.get("success"):
            return JSONResponse(
                content={
                    "code": 500,
                    "message": f"HDHive unlock failed: {unlock_data.get('message', 'unknown error')}",
                },
                status_code=500,
            )

        # Step 2: 从 unlock 返回值中提取真实的115链接
        real_url = unlock_data["data"].get("full_url", "")
        # URL 可能带有中文描述，需要截取纯链接部分
        # 格式: "https://115.com/s/xxx?password=yyy# 标题 访问码：xxx ..."
        real_url_clean = real_url.split(" ")[0] if " " in real_url else real_url
        logger.info(f"Real 115 URL: {real_url_clean}")

        # Step 3: 调用原始后端的转存接口（通过 localhost，跳过 Caddy 拦截）
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                save_resp = await client.post(
                    LOCAL_SAVE_URL,
                    json={"url": real_url_clean},
                )
                return JSONResponse(
                    content=save_resp.json(),
                    status_code=save_resp.status_code,
                )
            except Exception as e:
                logger.error(f"Save to 115 failed: {e}")
                return JSONResponse(
                    content={"code": 500, "message": f"Save failed: {e}"},
                    status_code=500,
                )
    else:
        # ---- 兼容旧流程: 直接转发到原始后端 ----
        logger.info(f"Legacy save URL: {raw_url}")
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                save_resp = await client.post(
                    LOCAL_SAVE_URL,
                    json={"url": raw_url},
                )
                return JSONResponse(
                    content=save_resp.json(),
                    status_code=save_resp.status_code,
                )
            except Exception as e:
                logger.error(f"Legacy save failed: {e}")
                return JSONResponse(
                    content={"code": 500, "message": f"Legacy save failed: {e}"},
                    status_code=500,
                )


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8900)
