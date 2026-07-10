# ALONE-CODER
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

class XBitAPI:
    def __init__(self):
        from Lily import config
        self.api_key = config.XBIT_API_TOKEN
        self.base_url = config.XBIT_API_URL

    async def get_info(self, vid_id: str):
        if not self.api_key:
            return None
        
        endpoint = f"{self.base_url}/info/{vid_id}"
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success':
                            return data
        except Exception as e:
            logger.error("[xbit][get_info] EXCEPTION vid_id=%s type=%s error=%s", vid_id, type(e).__name__, e)
        
        return None

    async def get_stream_url(self, vid_id: str, video: bool = False) -> str | None:
        if not self.api_key:
            return None
        data = await self.get_info(vid_id)
        if data:
            return data.get("video_url") if video else data.get("audio_url")
        return None

    async def search(self, query: str, message_id: int, video: bool = False):
        if not self.api_key:
            return None
        
        endpoint = f"{self.base_url}/search"
        params = {'query': query}
        headers = {'x-api-key': self.api_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success' and data.get('results'):
                            from Lily.helpers._dataclass import Media
                            from Lily.helpers import utils
                            res = data['results'][0]
                            return Media(
                                id=res['id'],
                                title=res['title'],
                                duration=utils.format_duration(res['duration_sec']),
                                duration_sec=res['duration_sec'],
                                url=res['url'],
                                file_path=None,
                                message_id=message_id,
                                video=video
                            )
        except Exception as e:
            logger.error("[xbit][search] EXCEPTION query=%s type=%s error=%s", query, type(e).__name__, e)
        return None

    async def playlist(self, limit: int, mention: str, url: str, video: bool = False):
        if not self.api_key:
            return None
        
        endpoint = f"{self.base_url}/playlist"
        params = {'url': url, 'limit': limit}
        headers = {'x-api-key': self.api_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success' and data.get('results'):
                            from Lily.helpers._dataclass import Track
                            from Lily.helpers import utils
                            tracks = []
                            for res in data['results']:
                                tracks.append(Track(
                                    id=res['id'],
                                    channel_name=res.get('channel', "Unknown"),
                                    duration=utils.format_duration(res['duration_sec']),
                                    duration_sec=res['duration_sec'],
                                    title=res['title'],
                                    url=res['url'],
                                    user=mention,
                                    video=video
                                ))
                            return tracks
        except Exception as e:
            logger.error("[xbit][playlist] EXCEPTION url=%s type=%s error=%s", url, type(e).__name__, e)
        return None

    async def download(self, vid_id: str, video: bool = False):
        path = f"downloads/{vid_id}.{'mp4' if video else 'mp3'}"
        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            logger.info("[xbit][download] Cache hit for vid_id=%s", vid_id)
            return path

        if not self.api_key:
            logger.warning("[xbit][download] No API key configured — skipping")
            return None

        logger.info("[xbit][download] Fetching info for vid_id=%s", vid_id)
        data = await self.get_info(vid_id)
        if not data:
            logger.error("[xbit][download] FAILED — get_info returned nothing for vid_id=%s", vid_id)
            return None

        url = data.get("video_url") if video else data.get("audio_url")
        if not url:
            logger.error("[xbit][download] FAILED — no stream URL in info for vid_id=%s data=%s", vid_id, data)
            return None

        logger.info("[xbit][download] Downloading from url=%s for vid_id=%s", url, vid_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        with open(path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                        file_size = os.path.getsize(path) if os.path.exists(path) else 0
                        if file_size > 1024:
                            logger.info("[xbit][download] ✓ vid_id=%s saved to %s (%d bytes)", vid_id, path, file_size)
                            return path
                        else:
                            logger.error("[xbit][download] FAILED — file too small or missing vid_id=%s size=%d", vid_id, file_size)
                    else:
                        try:
                            err_body = await response.text()
                        except Exception:
                            err_body = "<unreadable>"
                        logger.error(
                            "[xbit][download] FAILED — vid_id=%s status=%s body=%s",
                            vid_id, response.status, err_body[:300],
                        )
        except Exception as e:
            logger.error(
                "[xbit][download] EXCEPTION — vid_id=%s type=%s error=%s",
                vid_id, type(e).__name__, e,
            )

        return None
