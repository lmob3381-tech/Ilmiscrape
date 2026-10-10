import os
import re
import yt_dlp
import uuid
import json
import httpx
from typing import Dict, Any, Optional

def search_xnxx(query, limit=20):
    if query.startswith("#"):
        query = query[1:].strip()
    
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(f"https://www.xnxx.com/search/{query}")
            html = res.text
    except Exception as e:
        print(f"[XNXX] Search error: {e}")
        return []
        
    videos = []
    parts = html.split('<div id="video_')[1:]
    for part in parts:
        url_match = re.search(r'href="(/video-[^"]+)"', part)
        if not url_match:
            continue
        url = "https://www.xnxx.com" + url_match.group(1)
        vid_id = url_match.group(1).split("/")[1]
        
        title_match = re.search(r'title="([^"]+)"', part)
        title = title_match.group(1) if title_match else "Unknown"
        
        # Cari data-src atau fallback ke src yang bukan lightbox
        thumb_match = re.search(r'data-src="([^"]+)"', part)
        if not thumb_match:
            thumb_match = re.search(r'src="([^"]+)"', part)
        thumb = thumb_match.group(1) if thumb_match else ""
        if "lightbox" in thumb:
            thumb = ""
        if "THUMBNUM" in thumb:
            thumb = thumb.replace("THUMBNUM", "1")
        if thumb and "xnxx-cdn.com" in thumb:
            import urllib.parse
            thumb = "/api/thumb?url=" + urllib.parse.quote(thumb)
            
        duration_match = re.search(r'<span class="right">.*?</span>\s*([^<]+)\s*<span', part, re.DOTALL)
        duration_text = duration_match.group(1).strip().lower() if duration_match else "0"
        seconds = 0
        h = re.search(r'(\d+)\s*h', duration_text)
        m = re.search(r'(\d+)\s*min', duration_text)
        s = re.search(r'(\d+)\s*sec', duration_text)
        if h: seconds += int(h.group(1)) * 3600
        if m: seconds += int(m.group(1)) * 60
        if s: seconds += int(s.group(1))
        
        u_match = re.search(r'class="uploader"[^>]*>.*?<span class="name">([^<]+)</span>', part, re.DOTALL)
        if not u_match:
            u_match = re.search(r'<a\s+[^>]*href="/(?:porn-maker|profile|channel|model|uploader|pornstar|profiles|channels)/[^"]*"[^>]*>(?:<span[^>]*>)?([^<]+)(?:</span>)?</a>', part, re.I)
        uploader = u_match.group(1).strip() if u_match else "XNXX"

        videos.append({
            "title": title,
            "uploader": uploader,
            "duration": seconds,
            "thumbnail": thumb,
            "url": url,
            "id": vid_id,
            "platform": "xnxx"
        })
        if len(videos) >= limit:
            break
            
    return videos

def search_pornhub(query, limit=20):
    try:
        from curl_cffi import requests as c_requests
    except ImportError:
        print("[PornHub] curl_cffi not installed")
        return []

    page = 1
    if query.startswith("$$"):
        page_str = query.replace("$$", "").strip()
        page = int(page_str) if page_str.isdigit() else 1
        url = f"https://www.pornhub.com/video?page={page}"
    elif query.startswith("$"):
        q = query[1:].strip().replace(" ", "+")
        url = f"https://www.pornhub.com/video/search?search={q}&page=1"
    else:
        return []
        
    try:
        res = c_requests.get(url, impersonate="chrome110", timeout=10)
        html = res.text
    except Exception as e:
        print(f"[PornHub] Search error: {e}")
        return []

    import re
    videos = []
    blocks = re.findall(r'<li[^>]*class="[^"]*pcVideoListItem[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
    for b in blocks:
        t_match = re.search(r'title="([^"]+)"', b)
        title = t_match.group(1) if t_match else "Unknown"
        
        l_match = re.search(r'href="(/view_video\.php\?viewkey=[^"]+)"', b)
        if not l_match:
            continue
        link = "https://www.pornhub.com" + l_match.group(1)
        vid_id = l_match.group(1).split("viewkey=")[-1]
        
        th_match = re.search(r'data-mediumthumb="([^"]+)"', b) or re.search(r'src="([^"]+)"', b)
        thumb = th_match.group(1) if th_match else ""
        if "blank" in thumb or not thumb.startswith("http"):
             th_match = re.search(r'data-image="([^"]+)"', b) or re.search(r'data-src="([^"]+)"', b)
             if th_match:
                 thumb = th_match.group(1)
                 
        if thumb and "phncdn.com" in thumb:
            import urllib.parse
            thumb = "/api/thumb?url=" + urllib.parse.quote(thumb)

        d_match = re.search(r'<var class="duration">([^<]+)</var>', b)
        duration_text = d_match.group(1).strip() if d_match else "0"
        
        seconds = 0
        parts = duration_text.split(":")
        if len(parts) == 3:
            seconds = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2:
            seconds = int(parts[0])*60 + int(parts[1])
            
        u_match = re.search(r'class="usernameWrap".*?>([^<]+)</a>', b, re.DOTALL)
        if not u_match:
            u_match = re.search(r'data-mxptext="([^"]+)"', b)
        uploader = u_match.group(1).strip() if u_match else "Unknown"
        
        videos.append({
            "title": title,
            "uploader": uploader,
            "duration": seconds,
            "thumbnail": thumb,
            "url": link,
            "id": vid_id,
            "platform": "pornhub"
        })
        if len(videos) >= limit:
            break
            
    return videos

# YouTube memblokir IP datacenter ini ("Sign in to confirm you're not a bot").
# Semua request yt-dlp (metadata & pencarian) dirutekan lewat proxy — default
# Cloudflare WARP lokal di :40000. Set YTDLP_PROXY="" untuk mematikan.
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "socks5://127.0.0.1:40000")

OPTS = {
    "noplaylist": True,
    "quiet": True,
    "skip_download": True,
    "retries": 5,
    "socket_timeout": 15,
    "js_runtimes": {"node": {"path": "/usr/bin/node"}},
    "extractor_args": {"youtube": ["player_client=android,web"]},
    "format": "bestaudio/best"
}
if YTDLP_PROXY:
    OPTS["proxy"] = YTDLP_PROXY


def _extract(url: str, opts: dict):
    """Jalankan yt-dlp via proxy; fallback ke koneksi langsung bila proxy gagal."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        if opts.get("proxy"):
            print(f"[YTDLP] Gagal via proxy ({type(e).__name__}); coba koneksi langsung...")
            fallback = dict(opts)
            fallback.pop("proxy", None)
            with yt_dlp.YoutubeDL(fallback) as ydl:
                return ydl.extract_info(url, download=False)
        raise

def search_youtube(query: str, limit: int = 5):
    if query.strip().startswith("$$") or query.strip().startswith("$"):
        return search_pornhub(query, limit=10)
    if query.strip().startswith("#"):
        return search_xnxx(query, limit=10)
        
    print(f"[SEARCH] Query received: '{query}'")
    search_opts = OPTS.copy()
    search_opts['extract_flat'] = True

    videos = []
    try:
        info = _extract(f"ytsearch{limit}:{query}", search_opts)
        if info and 'entries' in info:
            entries_list = list(info['entries'])
            print(f"[SEARCH] Found {len(entries_list)} entries.")
            for entry in entries_list:
                url = entry.get('url') or entry.get('webpage_url', '')

                # Try to get the best thumbnail, or fallback to a generated url
                thumbnails = entry.get('thumbnails', [])
                thumbnail_url = thumbnails[0]['url'] if thumbnails else f"https://i.ytimg.com/vi/{entry.get('id', '')}/hqdefault.jpg"

                videos.append({
                    'title': entry.get('title', 'Unknown Title'),
                    'uploader': entry.get('uploader', 'Unknown'),
                    'duration': entry.get('duration', 0),
                    'thumbnail': thumbnail_url,
                    'url': url,
                    'id': entry.get('id', '')
                })
        else:
            print(f"[SEARCH] No 'entries' in info object: {info.keys() if info else 'None'}")
    except Exception as e:
        print(f"Error during search: {e}")

    return videos

def extract_tiktok(url: str) -> Dict[str, Any]:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        # TikWM requires no proxy, or direct access is fine
        with httpx.Client(timeout=15) as client:
            res = client.get(api_url)
            res.raise_for_status()
            data = res.json()

            if data.get("code") != 0 or not data.get("data"):
                raise ValueError("TikTok API error: " + data.get("msg", "Unknown error"))

            video_data = data["data"]

            formats = []

            # Video HD (jika tersedia, jika tidak pakai yang biasa)
            video_url = video_data.get("hdplay") or video_data.get("play")
            if video_url:
                formats.append({
                    "key": "mp4",
                    "label": "Video (MP4 - Resolusi Tertinggi)",
                    "ext": "mp4",
                    "url": video_url,
                    "size": video_data.get("hd_size") or video_data.get("size"),
                    "headers": {}
                })

            # Audio
            if video_data.get("music"):
                # Audio M4A (Original)
                formats.append({
                    "key": "m4a",
                    "label": "Audio (M4A - Original)",
                    "ext": "m4a",
                    "url": video_data["music"],
                    "size": None,
                    "headers": {}
                })
                # Audio MP3 (Transcoded/Standardized via backend)
                formats.append({
                    "key": "mp3",
                    "label": "Audio (MP3 - Standard)",
                    "ext": "mp3",
                    "url": video_data["music"],
                    "size": None,
                    "headers": {},
                    "duration": video_data.get("duration", 0)
                })

            return {
                "id": str(uuid.uuid4()),
                "platform": "tiktok",
                "title": video_data.get("title", "TikTok Video"),
                "duration": video_data.get("duration", 0),
                "thumbnail": video_data.get("cover", ""),
                "uploader": video_data.get("author", {}).get("nickname", "Unknown Uploader"),
                "formats": formats
            }
    except Exception as e:
        print(f"TikWM extraction failed: {e}")
        raise ValueError(f"Gagal mengekstrak TikTok. Pastikan URL valid dan video bersifat publik.")

def extract_info(url: str) -> Dict[str, Any]:
    if "tiktok.com" in url.lower():
        return extract_tiktok(url)

    info = _extract(url, OPTS)

    # Determine platform
    extractor = info.get("extractor", "").lower()
    if "youtube" in extractor:
        platform = "youtube"
    elif "tiktok" in extractor:
        platform = "tiktok"
    elif "xnxx" in extractor:
        platform = "xnxx"
    elif "pornhub" in extractor:
        platform = "pornhub"
    else:
        platform = "other"

    title = info.get("title", "Unknown Title")
    duration = info.get("duration", 0)
    thumbnail = info.get("thumbnail", "")
    uploader = info.get("uploader") or info.get("creator") or info.get("channel") or "Unknown Uploader"

    if platform in ("xnxx", "pornhub") and (not uploader or uploader.lower() in ("unknown uploader", "unknown", "xnxx", "pornhub")):
        try:
            with httpx.Client(timeout=5.0, proxy="socks5://127.0.0.1:40000" if platform == "pornhub" else None) as client:
                page_res = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.pornhub.com/" if platform == "pornhub" else "https://www.xnxx.com/"
                }, follow_redirects=True)
                if page_res.status_code == 200:
                    page_html = page_res.text
                    if platform == "xnxx":
                        m_up = re.search(r'<a\s+[^>]*href="/(?:porn-maker|profile|channel|model|uploader|pornstar|profiles|channels)/[^"]*"[^>]*>([^<]+)</a>', page_html, re.I)
                        if not m_up:
                            m_up = re.search(r'class="uploader"[^>]*>.*?<span class="name">([^<]+)</span>', page_html, re.DOTALL)
                        if m_up:
                            uploader = m_up.group(1).strip()
                    elif platform == "pornhub":
                        m_up = re.search(r'class="usernameBadgesWrapper"[^>]*>.*?<a[^>]+href="[^"]*"[^>]*>([^<]+)</a>', page_html, re.DOTALL)
                        if not m_up:
                            m_up = re.search(r'<span class="usernameWrap"[^>]*>.*?<a[^>]*>([^<]+)</a>', page_html, re.DOTALL)
                        if not m_up:
                            m_up = re.search(r'class="bolded">([^<]+)</a>', page_html)
                        if m_up:
                            uploader = m_up.group(1).strip()
        except Exception:
            pass

    formats = []

    if platform == "youtube":
        # Get best audio M4A
        m4a_format = next((f for f in reversed(info.get("formats", [])) if f.get("ext") == "m4a" and f.get("vcodec") == "none"), None)
        if m4a_format:
            formats.append({
                "key": "m4a",
                "label": "Audio (M4A - Original)",
                "ext": "m4a",
                "url": m4a_format["url"],
                "size": m4a_format.get("filesize") or m4a_format.get("filesize_approx"),
                "headers": m4a_format.get("http_headers", {}),
                "abr": m4a_format.get("abr", 128)
            })

            # MP3 options will be transcoded from this best audio URL in the backend
            formats.append({
                "key": "mp3",
                "label": "Audio (MP3 - 320kbps)",
                "ext": "mp3",
                "url": m4a_format["url"],  # Use same source URL for piping to ffmpeg
                "size": None, # Unknown size due to transcode
                "headers": m4a_format.get("http_headers", {}),
                "abr": 320,
                "duration": duration
            })

    elif platform == "tiktok":
        # Gunakan resolusi tertinggi (reverse order of formats) dan tanpa watermark jika memungkinkan
        best_video = next((f for f in reversed(info.get("formats", [])) if f.get("vcodec") != "none" and "watermark" not in f.get("format_note", "").lower()), None)
        if not best_video:
             best_video = next((f for f in reversed(info.get("formats", [])) if f.get("vcodec") != "none"), None)

        if best_video:
            formats.append({
                "key": "mp4",
                "label": "Video (MP4 - Resolusi Tertinggi)",
                "ext": "mp4",
                "url": best_video["url"],
                "size": best_video.get("filesize") or best_video.get("filesize_approx"),
                "headers": best_video.get("http_headers", {})
            })

        # Audio only
        best_audio = next((f for f in reversed(info.get("formats", [])) if f.get("vcodec") == "none"), None)
        if best_audio:
            formats.append({
                "key": "m4a",
                "label": "Audio (M4A - Original)",
                "ext": best_audio.get("ext", "m4a"),
                "url": best_audio["url"],
                "size": best_audio.get("filesize") or best_audio.get("filesize_approx"),
                "headers": best_audio.get("http_headers", {})
            })
            # Tambahkan format MP3 untuk TikTok agar dikonversi on-the-fly via backend
            formats.append({
                "key": "mp3",
                "label": "Audio (MP3 - Standard)",
                "ext": "mp3",
                "url": best_audio["url"],
                "size": None,
                "headers": best_audio.get("http_headers", {}),
                "duration": duration
            })

    elif platform == "xnxx" or platform == "pornhub":
        best_video = next((f for f in reversed(info.get("formats", [])) if "hls" in f.get("format_id", "").lower() or f.get("protocol") == "m3u8_native"), None)
        if not best_video:
            best_video = next((f for f in reversed(info.get("formats", [])) if f.get("protocol") == "https" and f.get("ext") == "mp4"), None)
        
        if best_video:
            url = best_video["url"]
            is_hls = "m3u8" in url
            size = best_video.get("filesize") or best_video.get("filesize_approx")
            if not is_hls and not size:
                try:
                    with httpx.Client(timeout=5.0, proxy="socks5://127.0.0.1:40000" if platform == "pornhub" else None) as client:
                        head_res = client.get(url, headers={
                            "Range": "bytes=0-0",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": "https://www.pornhub.com/" if platform == "pornhub" else "https://www.xnxx.com/"
                        })
                        if head_res.status_code in (206, 200):
                            cr = head_res.headers.get("content-range")
                            if cr:
                                m = re.search(r'/(\d+)$', cr)
                                if m: size = int(m.group(1))
                            elif "content-length" in head_res.headers and head_res.status_code == 200:
                                size = int(head_res.headers["content-length"])
                except:
                    pass
            
            formats.append({
                "key": "hls" if is_hls else "mp4",
                "label": "Video (HD)" if is_hls else "Video (MP4)",
                "ext": "m3u8" if is_hls else "mp4",
                "url": url,
                "size": size,
                "headers": best_video.get("http_headers", {})
            })

    # Fallback if no formats matched our strict criteria
    if not formats:
        best = info.get("url")
        if best:
             formats.append({
                "key": "best",
                "label": "Best Available",
                "ext": info.get("ext", "mp4"),
                "url": best,
                "size": info.get("filesize") or info.get("filesize_approx"),
                "headers": info.get("http_headers", {})
            })

    if (platform == "xnxx" and thumbnail and "xnxx-cdn.com" in thumbnail) or (platform == "pornhub" and thumbnail and "phncdn.com" in thumbnail):
        import urllib.parse
        thumbnail = "/api/thumb?url=" + urllib.parse.quote(thumbnail)

    return {
        "id": str(uuid.uuid4()),
        "platform": platform,
        "title": title,
        "duration": duration,
        "thumbnail": thumbnail,
        "uploader": uploader,
        "formats": formats
    }
