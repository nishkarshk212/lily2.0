
import logging
import aiohttp
import os

logger = logging.getLogger(__name__)

class AruYTAPI:
    def __init__(self):
        from Lily import config
        self.api_key = config.ARUYT_API_KEY
        self.base_url = config.ARUYT_API_URL

    async def get_info(self, vid_id: str):
        return None  # This API doesn't have info endpoint

    async def search(self, query: str, message_id: int, video: bool = False):
        return None  # This API doesn't have search endpoint

    async def playlist(self, limit: int, mention: str, url: str, video: bool = False):
        return None  # This API doesn't have playlist endpoint

    async def get_stream_url(self, vid_id: str, video: bool = False) -> str | None:
        if not self.api_key:
            return None
        url = f"{self.base_url}/download?api_key={self.api_key}&url=https://www.youtube.com/watch?v={vid_id}"
        if video:
            url += "&type=video"
        return url

    async def download(self, vid_id: str, video: bool = False):
        path = f"downloads/{vid_id}.{'mp4' if video else 'mp3'}"
        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            logger.info("[aruyt][download] Cache hit for vid_id=%s", vid_id)
            return path

        if not self.api_key:
            logger.warning("[aruyt][download] No API key configured — skipping")
            return None

        url = f"{self.base_url}/download?api_key={self.api_key}&url=https://www.youtube.com/watch?v={vid_id}"
        if video:
            url += "&type=video"

        logger.info("[aruyt][download] Downloading vid_id=%s from AruYT", vid_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        with open(path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                        file_size = os.path.getsize(path) if os.path.exists(path) else 0
                        if file_size > 1024:
                            logger.info("[aruyt][download] ✓ vid_id=%s saved to %s (%d bytes)", vid_id, path, file_size)
                            return path
                        else:
                            logger.error("[aruyt][download] FAILED — file too small or missing vid_id=%s size=%d", vid_id, file_size)
                    else:
                        try:
                            err_body = await response.text()
                        except Exception:
                            err_body = "<unreadable>"
                        logger.error(
                            "[aruyt][download] FAILED — vid_id=%s status=%s body=%s",
                            vid_id, response.status, err_body[:300],
                        )
        except Exception as e:
            logger.error(
                "[aruyt][download] EXCEPTION — vid_id=%s type=%s error=%s",
                vid_id, type(e).__name__, e,
            )

        return None
