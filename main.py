import json
import asyncio
import os
import re
import time
import hashlib
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

import aiofiles

LIMITS_FILE = "/root/clipgrab/limits.json"
limits_lock = asyncio.Lock()

async def load_local_limits():
    if not os.path.exists(LIMITS_FILE):
        return {}
    try:
        async with aiofiles.open(LIMITS_FILE, mode='r') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    except Exception:
        return {}

async def save_local_limits(data):
    try:
        async with aiofiles.open(LIMITS_FILE, mode='w') as f:
            await f.write(json.dumps(data))
    except Exception:
        pass

def get_usage_keys(ip: str, device_id: str, today: str):
    """Use a browser-stable ID for usage; retain IP keys for older clients."""
    if device_id:
        return (
            f"limit_count:device:{device_id}:{today}",
            f"limit_duration:device:{device_id}:{today}",
            f"limit_count:{ip}:{today}",
            f"limit_duration:{ip}:{today}",
        )
    return (
        f"limit_count:{ip}:{today}",
        f"limit_duration:{ip}:{today}",
        None,
        None,
    )

async def check_limits(ip: str, device_id: str = "", duration_to_add: int = 0, is_info_request: bool = False):
    """Check daily limits and increment usage, stable across IP changes."""
    today = datetime.now().strftime("%Y-%m-%d")
    count_key, duration_key, legacy_count_key, legacy_duration_key = get_usage_keys(ip, device_id, today)

    is_unlocked = False
    now = int(time.time())
    
    # We use local JSON file exclusively for Easter Egg to ensure device persistence
    # independent of Redis memory wipes.
    async with limits_lock:
        limits_data = await load_local_limits()
        
        if device_id:
            egg_key = f"easter_egg:{device_id}"
            claim_data = limits_data.get(egg_key)
            if claim_data:
                claimed_at = claim_data.get("claimed_at", 0)
                # Active for 3 days (3 * 86400 seconds)
                if now < claimed_at + 259200:
                    is_unlocked = True

        migration_key = f"usage_migrated:{device_id}:{today}" if device_id else None
        if legacy_count_key and migration_key not in limits_data:
            limits_data[count_key] = max(limits_data.get(count_key, 0), limits_data.get(legacy_count_key, 0))
            limits_data[duration_key] = max(limits_data.get(duration_key, 0), limits_data.get(legacy_duration_key, 0))
            limits_data[migration_key] = True

        current_count = limits_data.get(count_key, 0)
        current_duration = limits_data.get(duration_key, 0)
        
        LIMIT_COUNT = 99999 if is_unlocked else 20
        LIMIT_DURATION = 18000 if is_unlocked else 7200  # 5 hours or 2 hours

        if is_info_request and current_count >= LIMIT_COUNT:
            raise HTTPException(status_code=429, detail=f"Batas harian tercapai.")
            
        if duration_to_add > 0:
            if current_duration + duration_to_add > LIMIT_DURATION:
                raise HTTPException(status_code=429, detail=f"Batas durasi harian tercapai.")
                
        if is_info_request:
            limits_data[count_key] = current_count + 1
        if duration_to_add > 0:
            limits_data[duration_key] = current_duration + duration_to_add
            
        await save_local_limits(limits_data)

from pydantic import BaseModel
import httpx
import anyio
import redis.asyncio as redis_async
from redis.exceptions import ConnectionError as RedisConnectionError
import yt_dlp
from extractor import extract_info, search_youtube

app = FastAPI(title="IlmiDev Downloader API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Persistent connection pool for high-speed HLS proxying
hls_limits = httpx.Limits(max_keepalive_connections=30, max_connections=60, keepalive_expiry=120.0)
hls_client_direct = httpx.AsyncClient(limits=hls_limits, follow_redirects=True, timeout=20.0)
hls_client_proxy = httpx.AsyncClient(proxy="socks5://127.0.0.1:40000", limits=hls_limits, follow_redirects=True, timeout=20.0)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
try:
    cache = redis_async.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
except Exception:
    cache = None

class URLRequest(BaseModel):
    url: str
    device_id: str = ""

class SearchRequest(BaseModel):
    query: str
    device_id: str = ""

@app.post("/api/search")
async def search_yt(req: SearchRequest):
    try:
        results = await asyncio.to_thread(search_youtube, req.query)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/proxy_hls")
async def proxy_hls(url: str, request: Request):
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    
    client = hls_client_direct if "xnxx-cdn.com" in url else hls_client_proxy
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Referer": "https://www.pornhub.com/" if "phncdn.com" in url else "https://www.xnxx.com/"
    }

    if ".m3u8" in url:
        res = await client.get(url, headers=headers)
        text = res.text
        lines = text.split("\n")
        new_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                abs_url = urllib.parse.urljoin(url, line)
                encoded = urllib.parse.quote(abs_url, safe="")
                new_lines.append(f"/api/proxy_hls?url={encoded}")
            elif line.startswith("#") and "URI=\"" in line:
                def rewrite_uri(match):
                    abs_url = urllib.parse.urljoin(url, match.group(1))
                    encoded = urllib.parse.quote(abs_url, safe="")
                    return f'URI="/api/proxy_hls?url={encoded}"'
                new_lines.append(re.sub(r'URI="([^"]+)"', rewrite_uri, line))
            else:
                new_lines.append(line)
        rewritten = "\n".join(new_lines).encode("utf-8")
        return Response(
            content=rewritten,
            media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "no-cache, no-store"}
        )

    # For TS video segments: forward Content-Length and stream in 256KB chunks
    req_headers = dict(headers)
    range_header = request.headers.get("Range")
    if range_header:
        req_headers["Range"] = range_header

    upstream_req = client.build_request("GET", url, headers=req_headers)
    res = await client.send(upstream_req, stream=True)

    res_headers = {
        "Cache-Control": "public, max-age=86400",
        "Accept-Ranges": "bytes"
    }
    if "content-length" in res.headers:
        res_headers["Content-Length"] = res.headers["content-length"]
    if "content-range" in res.headers:
        res_headers["Content-Range"] = res.headers["content-range"]

    async def stream_ts():
        try:
            async for chunk in res.aiter_bytes(256 * 1024):
                yield chunk
        finally:
            await res.aclose()

    return StreamingResponse(
        stream_ts(),
        status_code=res.status_code,
        media_type="video/MP2T",
        headers=res_headers
    )

@app.get("/api/thumb")
async def proxy_thumb(url: str):
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    
    # We can use the same proxy settings as yt-dlp
    proxy = "socks5://127.0.0.1:40000"
    if "xnxx-cdn.com" in url or "tikwm.com" in url or "phncdn.com" in url:
        proxy = None
        
    async def fetch_thumb():
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Referer": "https://www.pornhub.com/" if "phncdn.com" in url else "https://www.xnxx.com/"
        }
        async with httpx.AsyncClient(proxy=proxy, follow_redirects=True, timeout=10.0) as client:
            async with client.stream("GET", url, headers=headers) as res:
                if res.status_code != 200:
                    yield b""
                    return
                async for chunk in res.aiter_bytes():
                    yield chunk
                    
    return StreamingResponse(fetch_thumb(), media_type="image/jpeg")

@app.get("/")
async def serve_index():
    response = FileResponse("static/index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"
    return response

@app.post("/api/info")
async def get_info(req: URLRequest, request: Request):
    ip = get_client_ip(request)
    await check_limits(ip, device_id=req.device_id, is_info_request=True)
    
    try:
        # Run synchronous yt-dlp in a thread to not block the event loop
        meta = await asyncio.to_thread(extract_info, req.url)

        # Cache for 5 minutes
        if cache:
            try:
                await cache.setex(f"info:{meta['id']}", 300, json.dumps(meta))
            except RedisConnectionError:
                # Redis not available, use local fallback
                app.state.local_cache = getattr(app.state, 'local_cache', {})
                app.state.local_cache[meta['id']] = meta
        else:
            # Fallback for local testing without redis
            app.state.local_cache = getattr(app.state, 'local_cache', {})
            app.state.local_cache[meta['id']] = meta

        return meta
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

import urllib.parse

def sanitize_filename(name: str) -> str:
    # Remove invalid filesystem characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace newlines
    name = name.replace('\n', ' ').replace('\r', '')
    # Encode for latin-1 header safety, replacing weird characters with standard ones or ignoring them
    # Better: just use ASCII representation
    return name.encode("ascii", "ignore").decode("ascii").strip() or "video"

async def get_ranged_stream(url: str, headers: dict, size: int = None, client_start: int = 0, client_end: int = None):
    proxy = "socks5://127.0.0.1:40000"
    if "xnxx-cdn.com" in url or "tikwm.com" in url:
        proxy = None
        
    CHUNK = 10 * 1024 * 1024  # 10MB Range
    READ = 1024 * 1024        # 1MB source read size
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(follow_redirects=True, timeout=None,
                                 proxy=proxy, limits=limits) as c:
        pos = client_start
        while True:
            end = pos + CHUNK - 1
            if size and end >= size:
                end = size - 1
            if client_end is not None and end > client_end:
                end = client_end

            req_headers = headers.copy()
            req_headers["Range"] = f"bytes={pos}-{end}"
            req_headers["Accept-Encoding"] = "identity"

            async with c.stream("GET", url, headers=req_headers) as r:
                if r.status_code not in (200, 206):
                    break

                bytes_read = 0
                async for chunk in r.aiter_bytes(READ):
                    bytes_read += len(chunk)
                    yield chunk

            pos += bytes_read

            if r.status_code == 200 or bytes_read < CHUNK or (size and pos >= size) or (client_end is not None and pos > client_end):
                break

async def stream_direct(url: str, headers: dict, size: int = None, start: int = 0, end: int = None):
    async for chunk in get_ranged_stream(url, headers, size, client_start=start, client_end=end):
        yield chunk

MP3_BITRATE = 320

async def stream_mp3_on_the_fly(url: str, headers: dict, meta: dict, start_time: float = 0.0):
    """Transcode and stream directly for immediate playback/download."""
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-threads", "0",
    ]
    if start_time > 0:
        cmd += ["-ss", f"{start_time:.3f}"]
        
    cmd += [
        "-i", "pipe:0",
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", f"{MP3_BITRATE}k",
        "-bufsize", "1M",
        "-metadata", f"title={meta.get('title', 'Unknown')}",
        "-metadata", f"artist={meta.get('uploader', 'Unknown')}",
        "-f", "mp3",
        "pipe:1"
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )

    async def write_to_ffmpeg():
        try:
            async for chunk in get_ranged_stream(url, headers, meta.get("size")):
                if process.stdin.is_closing():
                    break
                process.stdin.write(chunk)
                await process.stdin.drain()
        except Exception:
            pass
        finally:
            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()

    writer_task = asyncio.create_task(write_to_ffmpeg())

    try:
        while True:
            chunk = await process.stdout.read(256 * 1024)
            if not chunk:
                break
            yield chunk
    finally:
        if not writer_task.done():
            writer_task.cancel()
        if process.returncode is None:
            try:
                process.terminate()
            except OSError:
                pass

async def _load_meta(id: str):
    meta = None
    if cache:
        try:
            cached_meta = await cache.get(f"info:{id}")
            if cached_meta:
                meta = json.loads(cached_meta)
        except RedisConnectionError:
            meta = getattr(app.state, 'local_cache', {}).get(id)
    else:
        meta = getattr(app.state, 'local_cache', {}).get(id)
    return meta



async def track_stream(generator, dl_id: str):
    if not hasattr(app.state, "dl_status"):
        app.state.dl_status = {}
    if dl_id:
        app.state.dl_status[dl_id] = "downloading"
    try:
        async for chunk in generator:
            yield chunk
        if dl_id:
            app.state.dl_status[dl_id] = "completed"
    except BaseException:
        if dl_id:
            app.state.dl_status[dl_id] = "completed"

@app.get("/api/dl_status")
async def get_dl_status(dl_id: str):
    if not hasattr(app.state, "dl_status"):
        return {"status": "unknown"}
    status = app.state.dl_status.get(dl_id, "unknown")
    if status in ["completed", "error"]:
        app.state.dl_status.pop(dl_id, None)
    return {"status": status}


@app.api_route("/api/dl", methods=["GET", "HEAD"])
async def download(request: Request, id: str, fmt: str, stream: int = 0, device_id: str = "", dl_id: str = ""):
    # Retrieve from cache
    meta = None
    if cache:
        try:
            cached_meta = await cache.get(f"info:{id}")
            if cached_meta:
                meta = json.loads(cached_meta)
        except RedisConnectionError:
            # Fallback to local cache if Redis fails
            meta = getattr(app.state, 'local_cache', {}).get(id)
    else:
        meta = getattr(app.state, 'local_cache', {}).get(id)

    if not meta:
        raise HTTPException(status_code=404, detail="Session expired or not found. Please extract again.")

    # Find chosen format
    chosen = next((f for f in meta["formats"] if f["key"] == fmt), None)
    if not chosen:
        raise HTTPException(status_code=400, detail="Format not found")

    title = sanitize_filename(f"{meta['title']} - {meta['uploader']}")
    ext = chosen["ext"]
    filename = f"{title}.{ext}"

    # Check and deduct daily duration limit only for actual downloads
    if stream == 0:
        duration = meta.get("duration") or chosen.get("duration") or 0
        if duration > 0:
            ip = get_client_ip(request)
            await check_limits(ip, device_id=device_id, duration_to_add=duration)

    media_type = "application/octet-stream"
    if ext == "mp4":
        media_type = "video/mp4"
    elif ext == "mp3":
        media_type = "audio/mpeg"
    elif ext in ["m4a", "aac"]:
        media_type = "audio/mp4"

    # Streaming Headers
    encoded_filename = urllib.parse.quote(filename)
    disposition = "inline" if stream else "attachment"
    res_headers = {
        "Content-Disposition": f"{disposition}; filename=\"{sanitize_filename(filename)}\"; filename*=UTF-8''{encoded_filename}"
    }

    if stream and fmt != "mp3":
        res_headers["Accept-Ranges"] = "none"

    if fmt == "mp3":
        duration = meta.get("duration") or chosen.get("duration")
        if duration:
            res_headers["X-Duration"] = str(int(duration))
            
        res_headers["Accept-Ranges"] = "bytes"
        start_time = 0.0
        
        if stream:
            # Mode player web (instant play dengan seek approximate via ffmpeg)
            # Karena MP3 ini di-transcode langsung (on-the-fly), kita pakai chunked encoding (tanpa Content-Length fix).
            # Estimasi ukuran total untuk keperluan seek di player:
            est_total = int(duration * (MP3_BITRATE * 1000 // 8)) + 8192 if duration else None
            
            range_header = request.headers.get("range") if request else None
            if range_header and est_total:
                m = re.match(r"bytes=(\d+)-", range_header.strip())
                if m:
                    start_byte = int(m.group(1))
                    start_time = max(0.0, start_byte / (MP3_BITRATE * 1000 // 8))
                    
                    # Kita tetap beri tahu browser perkiraan Content-Range dan Content-Length
                    res_headers["Content-Range"] = f"bytes {start_byte}-{est_total-1}/{est_total}"
                    res_headers["Content-Length"] = str(est_total - start_byte)
                    return StreamingResponse(
                        (track_stream(stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta, start_time=start_time), dl_id) if stream == 0 and dl_id else stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta, start_time=start_time)),
                        status_code=206, media_type=media_type, headers=res_headers
                    )

            if est_total:
                # Beri hint ukuran ke player agar slider waktu (duration) muncul
                res_headers["Content-Range"] = f"bytes 0-{est_total-1}/{est_total}"
                res_headers["Content-Length"] = str(est_total)

            return StreamingResponse(
                (track_stream(stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta, start_time=start_time), dl_id) if stream == 0 and dl_id else stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta, start_time=start_time)),
                status_code=206 if est_total else 200, media_type=media_type, headers=res_headers
            )
        else:
            # Mode download (full dari 0, instant stream)
            res_headers["Accept-Ranges"] = "none"
            return StreamingResponse(
                (track_stream(stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta), dl_id) if stream == 0 and dl_id else stream_mp3_on_the_fly(chosen["url"], chosen["headers"], meta)),
                media_type=media_type, headers=res_headers
            )
    else:
        # Pass file size if available for direct stream
        size = chosen.get("size")
        start, end = 0, None
        
        if size:
            res_headers["Accept-Ranges"] = "bytes"
            res_headers["Content-Length"] = str(size)
            
            range_header = request.headers.get("range") if request else None
            if range_header:
                m = re.match(r"bytes=(\d+)-(\d*)", range_header.strip())
                if m:
                    start = int(m.group(1))
                    end_s = m.group(2)
                    end = int(end_s) if end_s else size - 1
                    if start >= size:
                        raise HTTPException(status_code=416, detail="Range Not Satisfiable")
                    end = min(end, size - 1)
                    
                    res_headers["Content-Range"] = f"bytes {start}-{end}/{size}"
                    res_headers["Content-Length"] = str(end - start + 1)
                    
                    return StreamingResponse(
                        (track_stream(stream_direct(chosen["url"], chosen["headers"], size=size, start=start, end=end), dl_id) if stream == 0 and dl_id else stream_direct(chosen["url"], chosen["headers"], size=size, start=start, end=end)),
                        status_code=206, media_type=media_type, headers=res_headers
                    )

        return StreamingResponse(
            (track_stream(stream_direct(chosen["url"], chosen["headers"], size=size, start=start, end=end), dl_id) if stream == 0 and dl_id else stream_direct(chosen["url"], chosen["headers"], size=size, start=start, end=end)),
            media_type=media_type, headers=res_headers
        )

@app.get("/api/limits")
async def get_limits(request: Request, device_id: str = ""):
    ip = get_client_ip(request)
    today = datetime.now().strftime("%Y-%m-%d")
    count_key, duration_key, legacy_count_key, legacy_duration_key = get_usage_keys(ip, device_id, today)
    
    current_count = 0
    current_duration = 0
    is_unlocked = False
    now = int(time.time())

    # Persistent Local JSON checks
    async with limits_lock:
        limits_data = await load_local_limits()
        migration_key = f"usage_migrated:{device_id}:{today}" if device_id else None
        if legacy_count_key and migration_key not in limits_data:
            limits_data[count_key] = max(limits_data.get(count_key, 0), limits_data.get(legacy_count_key, 0))
            limits_data[duration_key] = max(limits_data.get(duration_key, 0), limits_data.get(legacy_duration_key, 0))
            limits_data[migration_key] = True
            await save_local_limits(limits_data)
    if device_id:
        egg_key = f"easter_egg:{device_id}"
        claim_data = limits_data.get(egg_key)
        if claim_data:
            claimed_at = claim_data.get("claimed_at", 0)
            if now < claimed_at + 259200:
                is_unlocked = True

    current_count = limits_data.get(count_key, 0)
    current_duration = limits_data.get(duration_key, 0)
        
    return {
        "ip": ip,
        "count": current_count,
        "max_count": 99999 if is_unlocked else 20,
        "duration": current_duration,
        "max_duration": 18000 if is_unlocked else 7200
    }

class UnlockRequest(BaseModel):
    device_id: str

@app.post("/api/unlock")
async def unlock_limits(req: UnlockRequest):
    now = int(time.time())
    egg_key = f"easter_egg:{req.device_id}"
    
    async with limits_lock:
        limits_data = await load_local_limits()
        claim_data = limits_data.get(egg_key)
        
        if claim_data:
            claimed_at = claim_data.get("claimed_at", 0)
            # Active for 3 days = 3 * 86400 = 259200
            # Cooldown is 5 days after active = 8 * 86400 = 691200
            if now < claimed_at + 691200:
                if now < claimed_at + 259200:
                    return {"status": "active"}
                else:
                    raise HTTPException(status_code=400, detail="Easter egg sedang dalam masa cooldown (tunggu 5 hari lagi).")
                    
        # Claim
        limits_data[egg_key] = {"claimed_at": now}
        await save_local_limits(limits_data)
        
    return {"status": "unlocked"}

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse("static/manifest.json", media_type="application/manifest+json")

@app.get("/sw.js")
async def serve_sw():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.get("/health")
async def health():
    return {"status": "ok", "version": yt_dlp.version.__version__}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
