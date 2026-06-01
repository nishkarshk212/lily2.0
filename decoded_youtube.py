# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License
# This file is part of LilyMusic
# ALONE-CODE

import os
import re
import asyncio
import aiohttp
import random
import yt_dlp
from py_yt import Playlist, VideosSearch
from Lily import logger
from Lily.helpers import Track, utils

API_URL = "https://shrutibots.site"
DOWNLOAD_DIR = "downloads"

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "Lily/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def get_cookies(self):
        if not self.checked:
            if os.path.exists(self.cookie_dir):
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        if not os.path.exists(self.cookie_dir):
            os.makedirs(self.cookie_dir)
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = "https://batbin.me/api/v2/paste/" + url.split("/")[-1]
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        if not video_id or len(video_id) < 11:
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        ext = "mp4" if video else "mp3"
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

        if os.path.exists(file_path):
            return file_path

        # Try local yt-dlp first as it's more reliable than the external API
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best' if video else 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                'quiet': True,
                'no_warnings': True,
            }
            if not video:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            cookie_file = self.get_cookies()
            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file

            def _dl():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            await asyncio.to_thread(_dl)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
        except Exception as e:
            logger.warning(f"yt-dlp error: {e}")

        # Fallback to external API if yt-dlp fails
        try:
            async with aiohttp.ClientSession() as session:
                params = {"url": video_id, "type": "video" if video else "audio"}
                async with session.get(
                    f"{API_URL}/download",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()

                token = data.get("download_token")
                if not token:
                    return None

                stream_url = f"{API_URL}/stream/{video_id}?type={'video' if video else 'audio'}&token={token}"
                async with session.get(
                    stream_url,
                    timeout=aiohttp.ClientTimeout(total=600 if video else 300),
                ) as resp:
                    if resp.status == 302:
                        redirect_url = resp.headers.get('Location')
                        if redirect_url:
                            async with session.get(redirect_url) as final_resp:
                                if final_resp.status == 200:
                                    await self._write_file(file_path, final_resp)
                    elif resp.status == 200:
                        await self._write_file(file_path, resp)

                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
        except Exception as e:
            logger.warning(f"External API download error: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        return None

    async def _write_file(self, file_path, response):
        with open(file_path, "wb") as f:
            async for chunk in response.content.iter_chunked(16384):
                await asyncio.to_thread(f.write, chunk)
