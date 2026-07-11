# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of LilyMusic
#
# Download chain:
#   1. xBit API        (XBIT_API_URL / XBIT_API_TOKEN)
#   2. Railway YT API  (YT_API_BASE_URL / YT_API_KEY)

import asyncio
import glob
import os
import random
import re
import time as _time
from typing import Union

import aiohttp
from py_yt import Playlist, VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import yt_dlp

from Lily import config, logger
from Lily.helpers import utils

# ── Config ────────────────────────────────────────────────────────────────────
# xBit API  ─ primary downloader
XBIT_API_URL = getattr(config, "XBIT_API_URL", "https://tgapi.xbitcode.com")
XBIT_API_KEY = (
    getattr(config, "XBIT_API_TOKEN", None)
    or getattr(config, "XBIT_API_KEY", None)
    or getattr(config, "YT_API_KEY", None)
    or "xbit_40gZEycIlXXF38AlKKU4I96ZnNaiDFOV"  # bundled fallback key
)

# Railway YT API  ─ secondary downloader
RAILWAY_YT_API_URL = getattr(config, "YT_API_BASE_URL", None)
RAILWAY_YT_API_KEY = getattr(config, "YT_API_KEY", None)

DOWNLOAD_DIR = "downloads"


# Central cookie file produced from COOKIES_DATA at YouTube() startup.
COOKIE_0 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cookies", "cookie_0.txt"))


# ── Cookie helper ─────────────────────────────────────────────────────────────
def cookie_txt_file() -> str | None:
    """Return a cookie .txt file path to pass to yt-dlp.

    Prefers the decoded COOKIES_DATA file (cookie_0.txt); falls back to any
    other Netscape cookie file present in the cookies/ folder.
    """
    try:
        base_dir  = os.path.dirname(os.path.abspath(__file__))
        folder    = os.path.abspath(os.path.join(base_dir, "..", "cookies"))
        # COOKIES_DATA is the primary (and most reliable) credential source.
        if os.path.exists(COOKIE_0) and os.path.getsize(COOKIE_0) > 0:
            return COOKIE_0
        txt_files = glob.glob(os.path.join(folder, "*.txt"))
        # Exclude the logs file if it ever lands here
        txt_files = [f for f in txt_files if not f.endswith("logs.csv")]
        if not txt_files:
            return None
        chosen   = random.choice(txt_files)
        log_file = os.path.join(folder, "logs.csv")
        with open(log_file, "a") as f:
            f.write(f"Chosen: {chosen}\n")
        return chosen
    except Exception:
        return None


# ── Link helpers ──────────────────────────────────────────────────────────────
def _normalize_youtube_link(
    link: str,
    base: str = "https://www.youtube.com/watch?v=",
) -> str:
    if not link:
        return ""
    cleaned = link.strip()
    if "youtube.com" not in cleaned and "youtu.be" not in cleaned:
        cleaned = base + cleaned
    cleaned = cleaned.split("&si=")[0].split("?si=")[0]
    if "&" in cleaned and "list=" not in cleaned:
        cleaned = cleaned.split("&")[0]
    return cleaned


def _extract_video_id(link: str) -> str | None:
    cleaned = _normalize_youtube_link(link)
    if not cleaned:
        return None
    if "v=" in cleaned:
        return cleaned.split("v=")[-1].split("&")[0]
    if "youtu.be/" in cleaned:
        return cleaned.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    return cleaned if len(cleaned) == 11 else None




# ── Downloader 1: xBit API ───────────────────────────────────────────────────
async def _xbit_download(link: str, media_type: str) -> str | None:
    """
    Download via xBit API.
    GET {XBIT_API_URL}/info/{video_id}  →  {"status":"success","audio_url":...,"video_url":...}
    Then streams the direct URL to a local file.
    Returns local file path on success, None on failure.
    """
    video_id = _extract_video_id(link) or link
    if not video_id or len(video_id) < 3:
        return None

    ext        = "mp4" if media_type == "video" else "mp3"
    timeout_dl = 600   if media_type == "video" else 300
    file_path  = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    headers = {
        "x-api-key": str(XBIT_API_KEY),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{XBIT_API_URL}/info/{video_id}",
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    logger.warning("xBit info failed: status %s for %s", resp.status, video_id)
                    return None
                try:
                    data = await resp.json(content_type=None)
                except Exception as e:
                    logger.warning("xBit info returned invalid JSON: %s", e)
                    return None

            if data.get("status") != "success":
                logger.warning("xBit API error: %s", data.get("message", "unknown"))
                return None

            media_url = (
                data.get("video_url") if media_type == "video" else data.get("audio_url")
            )
            if not media_url:
                logger.warning("xBit: no %s_url in response", media_type)
                return None

            async with session.get(
                media_url,
                timeout=aiohttp.ClientTimeout(total=timeout_dl),
                allow_redirects=True,
            ) as file_resp:
                if file_resp.status != 200:
                    logger.warning("xBit stream failed: status %s", file_resp.status)
                    return None
                with open(file_path, "wb") as fobj:
                    async for chunk in file_resp.content.iter_chunked(1024 * 1024):
                        fobj.write(chunk)

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info("xBit API ✓ %s → %s", video_id, file_path)
            return file_path

        return None

    except Exception as exc:
        logger.warning("xBit download failed for %s: %s", video_id, exc)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
        return None


# yt-dlp 2026.x requires Node >= 23.5 to solve YouTube's n-signature challenge.
# It defaults to deno (which isn't installed), so we must force the node runtime explicitly.
YTDLP_JS_ARGS = ["--js-runtimes", "node"]

async def _railway_download(video_id: str, media_type: str) -> str | None:
    """
    Download via Railway self-hosted YouTube API.
    GET {RAILWAY_YT_API_URL}/play/audio?id=<video_id>  (audio)
    GET {RAILWAY_YT_API_URL}/play/video/hq?id=<video_id> then /play/video (video)
    Returns local file path on success, None on failure.
    """
    if not RAILWAY_YT_API_URL or not RAILWAY_YT_API_KEY:
        return None

    ext        = "mp4" if media_type == "video" else "mp3"
    timeout_dl = 600   if media_type == "video" else 300
    file_path  = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-API-Key": str(RAILWAY_YT_API_KEY),
    }
    endpoints = ["play/video/hq", "play/video"] if media_type == "video" else ["play/audio"]

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            for endpoint in endpoints:
                media_url = f"{RAILWAY_YT_API_URL}/{endpoint}?id={video_id}"
                logger.info("[download][railway] Trying endpoint: %s", media_url)
                async with session.get(
                    media_url,
                    timeout=aiohttp.ClientTimeout(total=timeout_dl),
                    allow_redirects=True,
                ) as file_resp:
                    if file_resp.status != 200:
                        try:
                            err_body = await file_resp.text()
                        except Exception:
                            err_body = "<unreadable>"
                        logger.error(
                            "[download][railway] FAILED — video_id=%s endpoint=%s status=%s body=%s",
                            video_id, endpoint, file_resp.status, err_body[:300],
                        )
                        continue
                    with open(file_path, "wb") as fobj:
                        async for chunk in file_resp.content.iter_chunked(1024 * 1024):
                            fobj.write(chunk)
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    if file_size > 0:
                        logger.info("[download][railway] ✓ video_id=%s saved to %s (%d bytes)", video_id, file_path, file_size)
                        return file_path
                    else:
                        logger.error(
                            "[download][railway] FAILED — video_id=%s endpoint=%s file saved but is empty (0 bytes)",
                            video_id, endpoint,
                        )
        logger.error("[download][railway] All endpoints exhausted for video_id=%s — falling back to next downloader", video_id)
        return None

    except Exception as exc:
        logger.error(
            "[download][railway] EXCEPTION — video_id=%s type=%s error=%s",
            video_id, type(exc).__name__, exc,
        )
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("[download][railway] Removed partial file: %s", file_path)
        except OSError:
            pass
        return None


# ── Local download fallback ──────────────────────────────────────────────────
async def _local_ytdlp_download(video_id: str, media_type: str) -> str | None:
    """
    Download via local yt-dlp.
    """
    import subprocess
    ext = "mp4" if media_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path
    url = f"https://www.youtube.com/watch?v={video_id}"
    cookie = cookie_txt_file()
    
    try:
        if media_type == "video":
            cmd = [
                "yt-dlp",
                *YTDLP_JS_ARGS,
                "-f", "best[height<=?720][width<=?1280]/best",
                "-o", os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            ]
            if cookie:
                cmd.extend(["--cookies", cookie])
            cmd.append(url)
        else:
            cmd = [
                "yt-dlp",
                *YTDLP_JS_ARGS,
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            ]
            if cookie:
                cmd.extend(["--cookies", cookie])
            cmd.append(url)

        logger.info("[download][local-ytdlp] Running: %s", ' '.join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode(errors="replace").strip() if stdout else ""
        stderr_text = stderr.decode(errors="replace").strip() if stderr else ""

        if proc.returncode != 0:
            logger.error(
                "[download][local-ytdlp] FAILED — video_id=%s returncode=%s stderr=%s",
                video_id, proc.returncode, stderr_text[-500:],
            )
        else:
            logger.info("[download][local-ytdlp] yt-dlp exited 0 for video_id=%s", video_id)

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info("[download][local-ytdlp] ✓ video_id=%s saved to %s (%d bytes)", video_id, file_path, os.path.getsize(file_path))
            return file_path

        for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*")):
            if os.path.getsize(f) > 0:
                if media_type == "video" and f.endswith((".mp4", ".mkv", ".webm")):
                    logger.info("[download][local-ytdlp] ✓ Found alternate file: %s", f)
                    return f
                elif media_type == "audio" and f.endswith((".mp3", ".m4a", ".webm")):
                    logger.info("[download][local-ytdlp] ✓ Found alternate file: %s", f)
                    return f

        logger.error(
            "[download][local-ytdlp] FAILED — video_id=%s no output file found after yt-dlp. stderr=%s",
            video_id, stderr_text[-500:],
        )

    except Exception as e:
        logger.error(
            "[download][local-ytdlp] EXCEPTION — video_id=%s type=%s error=%s",
            video_id, type(e).__name__, e,
        )

    return None


# ── Main download entrypoint ──────────────────────────────────────────────────
async def _download_with_fallback(
    link: str,
    media_type: str,
) -> tuple[str | None, str]:
    """
    Try downloaders in order:
      1. Local yt-dlp download (using cookies base64)
      2. Railway YT API (primary)
      3. xBit API (fallback)
    Returns (file_path, downloader_name)
    """
    video_id = _extract_video_id(link) or link
    logger.info("[download][fallback-chain] Starting download for video_id=%s media_type=%s", video_id, media_type)

    # 1. Local yt-dlp download (primary fallback)
    logger.info("[download][fallback-chain] Step 1/3 — trying local yt-dlp for video_id=%s", video_id)
    result = await _local_ytdlp_download(video_id, media_type)
    if result:
        logger.info("[download][fallback-chain] ✓ Local yt-dlp succeeded for video_id=%s", video_id)
        return result, "local"
    logger.warning("[download][fallback-chain] Local yt-dlp failed for video_id=%s — moving to Railway YT API", video_id)

    # 2. Railway YT API (secondary)
    logger.info("[download][fallback-chain] Step 2/3 — trying Railway YT API for video_id=%s", video_id)
    result = await _railway_download(video_id, media_type)
    if result:
        logger.info("[download][fallback-chain] ✓ Railway succeeded for video_id=%s", video_id)
        return result, "railway"
    logger.warning("[download][fallback-chain] Railway failed for video_id=%s — moving to xBit", video_id)

    # 3. xBit API (fallback)
    logger.info("[download][fallback-chain] Step 3/3 — trying xBit API for video_id=%s", video_id)
    result = await _xbit_download(link, media_type)
    if result:
        logger.info("[download][fallback-chain] ✓ xBit succeeded for video_id=%s", video_id)
        return result, "xbit"
    logger.warning("[download][fallback-chain] xBit failed for video_id=%s", video_id)

    logger.error(
        "[download][fallback-chain] ❌ ALL 3 download methods failed for video_id=%s media_type=%s",
        video_id, media_type,
    )
    return None, "none"


# ── Public helpers (kept for backward compat with play.py / calls.py) ─────────
async def download_song(link: str, title: str | None = None) -> str | None:
    path, _ = await _download_with_fallback(link, "audio")
    return path


async def download_video(link: str, title: str | None = None) -> str | None:
    path, _ = await _download_with_fallback(link, "video")
    return path


# ── YouTube class ─────────────────────────────────────────────────────────────
class YouTube:
    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.regex    = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg      = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.api      = None
        self.cookies_dir = os.path.join(os.path.dirname(__file__), "..", "cookies")

        # Dynamically load COOKIES_DATA env var if present (base64 cookies helper)
        cookies_data = getattr(config, "COOKIES_DATA", None) or os.environ.get("COOKIES_DATA")
        if cookies_data:
            try:
                import base64
                decoded = base64.b64decode(cookies_data).decode("utf-8")
                os.makedirs(self.cookies_dir, exist_ok=True)
                with open(os.path.join(self.cookies_dir, "cookie_0.txt"), "w") as f:
                    f.write(decoded)
                logger.info("Successfully loaded cookies from COOKIES_DATA environment variable.")
            except Exception as e:
                logger.error("Error decoding COOKIES_DATA environment variable: %s", e)

        self.dl_stats = {
            "total_requests": 0,
            "local":          0,
            "yt_api":         0,
            "xbit":           0,
            "aruyt":          0,
            "nexgen":         0,
            "railway":        0,
            "existing_files": 0,
            "failed":         0,
        }

    # ── Validators ────────────────────────────────────────────────────────────
    def valid(self, url: str) -> bool:
        return bool(re.search(self.regex, url))

    def invalid(self, url: str) -> bool:
        return not self.valid(url)

    # ── Cookie management ─────────────────────────────────────────────────────
    async def save_cookies(self, urls: list) -> None:
        if not urls:
            return
        os.makedirs(self.cookies_dir, exist_ok=True)
        try:
            async with aiohttp.ClientSession() as session:
                for i, url in enumerate(urls):
                    if not url:
                        continue
                    try:
                        async with session.get(
                            url, timeout=aiohttp.ClientTimeout(total=15)
                        ) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                path = os.path.join(self.cookies_dir, f"cookies_{i}.txt")
                                with open(path, "w") as f:
                                    f.write(content)
                                logger.info("Saved cookies → %s", path)
                            else:
                                logger.warning("Cookie fetch failed %s (status %s)", url, resp.status)
                    except Exception as e:
                        logger.warning("Cookie error from %s: %s", url, e)
        except Exception as e:
            logger.warning("save_cookies error: %s", e)

    # ── URL utilities ─────────────────────────────────────────────────────────
    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            text = message.text or message.caption or ""
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset: entity.offset + entity.length]
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    # ── Metadata fetchers ─────────────────────────────────────────────────────
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        results = VideosSearch(link, limit=1)
        r = (await results.next())["result"][0]
        title        = r["title"]
        duration_min = r["duration"]
        thumbnail    = r["thumbnails"][0]["url"].split("?")[0]
        vidid        = r["id"]
        duration_sec = int(utils.to_seconds(duration_min)) if duration_min else 0
        formatted_duration = utils.format_duration(duration_sec)
        return title, formatted_duration, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str | None:
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            return r["title"]
        return None

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str | None:
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            duration_str = r["duration"]
            duration_sec = int(utils.to_seconds(duration_str)) if duration_str else 0
            return utils.format_duration(duration_sec)
        return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str | None:
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            return r["thumbnails"][0]["url"].split("?")[0]
        return None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            duration_str = r["duration"]
            duration_sec = int(utils.to_seconds(duration_str)) if duration_str else 0
            track_details = {
                "title":        r["title"],
                "link":         r["link"],
                "vidid":        r["id"],
                "duration_min": utils.format_duration(duration_sec),
                "thumb":        r["thumbnails"][0]["url"].split("?")[0],
            }
            return track_details, r["id"]
        return None, None

    async def search(
        self,
        query: str,
        message_id: int,
        video: bool = False,
    ):
        """Search YouTube and return a Track dataclass or None.
        Prioritizes official studio versions, avoids remixes/covers/live etc.
        """
        from Lily.helpers import Track

        # Keywords to avoid in results unless explicitly in query
        avoid_keywords = [
            "remix", "cover", "live", "slowed", "reverb", "extended", "acoustic", 
            "instrumental", "karaoke", "8d", "bass boosted", "nightcore", "edit"
        ]
        
        # Check if query explicitly includes any avoid keyword
        query_lower = query.strip().lower()
        explicit_avoid = any(kw in query_lower for kw in avoid_keywords)

        try:
            # First try with "official audio" or "official video" modifier to prioritize official versions
            search_queries = [
                f"{query.strip()} official audio",
                f"{query.strip()} official video",
                query.strip()
            ] if not explicit_avoid else [query.strip()]

            for sq in search_queries:
                results = VideosSearch(sq, limit=10)  # Get more results to filter
                raw_results = (await results.next())["result"]
                if not raw_results:
                    continue

                # Filter results
                filtered = []
                for r in raw_results:
                    title_lower = r.get("title", "").lower()
                    
                    # Skip if any avoid keyword in title (unless explicit in query)
                    if not explicit_avoid:
                        if any(kw in title_lower for kw in avoid_keywords):
                            continue

                    # Check duration (skip very short/long)
                    duration_str = r.get("duration") or "0:00"
                    parts = duration_str.split(":")
                    try:
                        if len(parts) == 3:
                            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        elif len(parts) == 2:
                            secs = int(parts[0]) * 60 + int(parts[1])
                        else:
                            secs = 0
                    except (ValueError, IndexError):
                        secs = 0
                    
                    if 30 <= secs <= 3600:  # 30 sec to 1 hour
                        filtered.append(r)
                
                if filtered:
                    r = filtered[0]  # Take best match
                    vidid = r["id"]
                    duration_sec = secs
                    return Track(
                        id           = vidid,
                        title        = r["title"],
                        url          = r.get("link", self.base + vidid),
                        duration     = utils.format_duration(duration_sec),
                        duration_sec = duration_sec,
                        thumbnail    = r["thumbnails"][0]["url"].split("?")[0],
                        channel_name = (r.get("channel") or {}).get("name", ""),
                        message_id   = message_id,
                        video        = video,
                        time         = int(_time.time()),
                    )

            return None
        except Exception as e:
            logger.warning("YouTube search error for '%s': %s", query, e)
            return None

    # ── Slider ────────────────────────────────────────────────────────────────
    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link        = _normalize_youtube_link(link)
        search      = VideosSearch(link, limit=10)
        raw_results = (await search.next()).get("result", [])

        filtered = []
        for item in raw_results:
            duration_str = item.get("duration") or "0:00"
            parts = duration_str.split(":")
            try:
                if len(parts) == 3:
                    secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    secs = int(parts[0]) * 60 + int(parts[1])
                else:
                    secs = 0
            except (ValueError, IndexError):
                continue
            if 0 < secs <= 3600:
                filtered.append(item)

        if not filtered or query_type >= len(filtered):
            raise ValueError("No suitable videos found within duration limit")

        s = filtered[query_type]
        return s["title"], s.get("duration") or "0:00", s["thumbnails"][0]["url"].split("?")[0], s["id"]

    # ── Formats (yt-dlp) ──────────────────────────────────────────────────────
    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        ydl = yt_dlp.YoutubeDL({"quiet": True, "js_runtimes": {"node": {}}})
        with ydl:
            info = ydl.extract_info(link, download=False)
        formats_available = []
        for fmt in info.get("formats", []):
            try:
                if "dash" not in str(fmt["format"]).lower():
                    formats_available.append({
                        "format":      fmt["format"],
                        "filesize":    fmt.get("filesize"),
                        "format_id":   fmt["format_id"],
                        "ext":         fmt["ext"],
                        "format_note": fmt.get("format_note"),
                        "yturl":       link,
                    })
            except Exception:
                continue
        return formats_available, link

    # ── Video stream URL (yt-dlp, no download) ────────────────────────────────
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _normalize_youtube_link(link)
        cookie = cookie_txt_file()
        cmd = ["yt-dlp", *YTDLP_JS_ARGS, "-g", "-f", "best[height<=?720][width<=?1280]", link]
        if cookie:
            cmd.extend(["--cookies", cookie])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def get_stream_url(
        self,
        video_id: str,
        video: bool = False,
        title: str | None = None,
        duration: str | None = None,
        duration_sec: int | None = None,
    ) -> str | None:
        """
        Get a direct stream URL without downloading (for immediate playback).
        Tries sources in the configured PLAY_PRIORITY order and returns the
        first stream URL that works. Caches successful results (3h TTL).
        """
        from Lily import db, xbit, nexgen, yt_api, aruyt

        # Check cache first
        cache = await db.get_media_cache(video_id)
        if cache:
            import time
            cached_at = cache.get("cached_at", 0)
            # YouTube streaming URLs usually expire in 6 hours. Let's invalidate them after 3 hours (10800 seconds)
            if time.time() - cached_at < 10800:
                url = cache.get("video_url") if video else cache.get("audio_url")
                if url and (url.startswith("http://") or url.startswith("https://")):
                    logger.info("Using cached streaming URL for %s: %s", video_id, url)
                    return url

        # Define a helper to save cache
        async def save_to_cache(url: str):
            import time
            cache_data = {
                "title": title or "Unknown",
                "duration": duration or "0:00",
                "duration_sec": duration_sec or 0,
                ("video_url" if video else "audio_url"): url,
                "cached_at": time.time()
            }
            await db.save_media_cache(video_id, cache_data)

        cookie = cookie_txt_file()
        priority = config._play_priority_enabled()

        for key in priority:
            try:
                if key == "yt_api":
                    if not config.YT_API_BASE_URL:
                        continue
                    url = await yt_api.get_stream_url(video_id, video=video)
                    if url:
                        logger.info("Got streaming URL from YT API for %s: %s", video_id, url)
                        await save_to_cache(url)
                        return url

                elif key == "xbit":
                    if not config.XBIT_API_TOKEN:
                        continue
                    url = await xbit.get_stream_url(video_id, video=video)
                    if url:
                        logger.info("Got streaming URL from XBit for %s: %s", video_id, url)
                        await save_to_cache(url)
                        return url

                elif key == "aruyt":
                    if not config.ARUYT_API_KEY:
                        continue
                    url = await aruyt.get_stream_url(video_id, video=video)
                    if url:
                        logger.info("Got streaming URL from AruYT for %s: %s", video_id, url)
                        await save_to_cache(url)
                        return url

                elif key == "nexgen":
                    if not config.NEXGENBOTS_API_TOKEN:
                        continue
                    url = await nexgen.get_stream_url(video_id, video=video)
                    if url:
                        logger.info("Got streaming URL from NexGen for %s: %s", video_id, url)
                        await save_to_cache(url)
                        return url

                elif key == "local":
                    # Local yt-dlp always has the cookie (COOKIES_DATA) if set.
                    try:
                        cmd = ["yt-dlp", *YTDLP_JS_ARGS, "-g", "-f",
                               "bestvideo[height<=720]+bestaudio/best[height<=720]" if video else "bestaudio"]
                        if cookie:
                            cmd.extend(["--cookies", cookie])
                        cmd.append(f"https://www.youtube.com/watch?v={video_id}")

                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            stream_url = stdout.decode().split("\n")[0]
                            if stream_url:
                                logger.info("Extracted direct stream URL via yt-dlp: %s", video_id)
                                await save_to_cache(stream_url)
                                return stream_url
                    except Exception as e:
                        logger.warning("yt-dlp get_stream_url failed for %s: %s", video_id, e)
            except Exception as e:
                logger.warning("get_stream_url source '%s' failed for %s: %s", key, video_id, e)

        return None

    # ── Download (main method called by play.py / calls.py) ──────────────────
    async def download(
        self,
        video_id: str,
        video: bool = False,
        title: str | None = None,
    ) -> str | None:
        """
        Download audio/video by video_id.

        Uses the configured PLAY_PRIORITY chain: each source that is configured
        is asked for a stream URL; the winning URL is streamed to a local file.
        This lets operators prefer a fast live stream (e.g. local yt-dlp with
        cookies) or a hosted API, and download queued songs with the same order.
        Falls back to the legacy 3-method chain on any failure.
        """
        self.dl_stats["total_requests"] += 1
        link = _normalize_youtube_link(video_id, self.base)
        media_type = "video" if video else "audio"

        # 1) Try each configured priority source for a stream URL, then fetch it.
        try:
            priority = config._play_priority_enabled()
            from Lily import xbit, nexgen, yt_api, aruyt
            for key in priority:
                url = None
                try:
                    if key == "yt_api" and config.YT_API_BASE_URL and config.YT_API_KEY:
                        url = await yt_api.get_stream_url(video_id, video=video)
                    elif key == "xbit" and config.XBIT_API_TOKEN:
                        url = await xbit.get_stream_url(video_id, video=video)
                    elif key == "aruyt" and config.ARUYT_API_KEY:
                        url = await aruyt.get_stream_url(video_id, video=video)
                    elif key == "nexgen" and config.NEXGENBOTS_API_TOKEN:
                        url = await nexgen.get_stream_url(video_id, video=video)
                    elif key == "local":
                        url = await self._local_stream_url(video_id, video=video)
                except Exception as e:
                    logger.warning("download: source '%s' stream-url failed for %s: %s", key, video_id, e)
                    continue

                if not url or not (url.startswith("http://") or url.startswith("https://")):
                    continue

                # Stream the resolved URL to a local file.
                file_path = await self._fetch_stream_to_file(url, video_id, media_type)
                if file_path:
                    self.dl_stats[key] += 1
                    logger.info("YouTube.download success: %s (%s) via %s", video_id, media_type, key)
                    return file_path
        except Exception as e:
            logger.warning("YouTube.download priority chain error for '%s': %s", video_id, e)

        # 2) Legacy fallback chain (local yt-dlp → railway → xBit)
        try:
            result, downloader = await _download_with_fallback(link, media_type)
            if result:
                self.dl_stats[downloader] += 1
                logger.info("YouTube.download success: %s (%s) via %s", video_id, media_type, downloader)
                return result
        except Exception as e:
            logger.warning("YouTube.download fallback error for '%s': %s", video_id, e)

        self.dl_stats["failed"] += 1
        return None

    async def _local_stream_url(self, video_id: str, video: bool = False) -> str | None:
        """Resolve a direct stream URL from local yt-dlp (uses COOKIES_DATA)."""
        cookie = cookie_txt_file()
        try:
            cmd = ["yt-dlp", *YTDLP_JS_ARGS, "-g", "-f",
                   "bestvideo[height<=720]+bestaudio/best[height<=720]" if video else "bestaudio"]
            if cookie:
                cmd.extend(["--cookies", cookie])
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                return stdout.decode().split("\n")[0] or None
        except Exception as e:
            logger.warning("yt-dlp stream url failed for %s: %s", video_id, e)
        return None

    async def _fetch_stream_to_file(self, url: str, video_id: str, media_type: str) -> str | None:
        """Download a (possibly time-limited) stream URL to a local file."""
        import aiohttp as _aiohttp
        ext = "mp4" if media_type == "video" else "mp3"
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        try:
            timeout_dl = 600 if media_type == "video" else 300
            async with _aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=_aiohttp.ClientTimeout(total=timeout_dl), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("[fetch_stream] status %s for %s", resp.status, video_id)
                        return None
                    with open(file_path, "wb") as fobj:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            fobj.write(chunk)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info("[fetch_stream] ✓ %s saved to %s", video_id, file_path)
                return file_path
        except Exception as e:
            logger.warning("[fetch_stream] failed for %s: %s", video_id, e)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        return None

    # ── Playlist ──────────────────────────────────────────────────────────────
    async def playlist(
        self,
        limit: int,
        mention: str,
        link: str,
        video: bool = False,
    ) -> list:
        """Fetch playlist tracks, return list of Track dataclasses."""
        from Lily.helpers import Track

        link = _normalize_youtube_link(link)
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []

        tracks = []
        for data in (plist.get("videos") or [])[:limit]:
            if not data:
                continue
            vidid = data.get("id")
            if not vidid:
                continue
            duration_min = data.get("duration") or "00:00"
            duration_sec = int(utils.to_seconds(duration_min)) if duration_min else 0
            thumbs       = data.get("thumbnails") or []
            thumbnail    = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
            tracks.append(Track(
                id           = vidid,
                title        = data.get("title") or vidid,
                url          = data.get("link") or self.base + vidid,
                duration     = utils.format_duration(duration_sec),
                duration_sec = duration_sec,
                thumbnail    = thumbnail,
                user         = mention,
                video        = video,
                time         = int(_time.time()),
            ))
        return tracks
