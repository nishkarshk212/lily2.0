# Lily Coder
import aiohttp
import os
import subprocess
import json

class YTAPI:
    def __init__(self):
        from Lily import config
        self.base_url = config.YT_API_BASE_URL
        self.api_key = getattr(config, "YT_API_KEY", None)

    async def get_info(self, url_or_id: str):
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            vid_id = url_or_id.split("v=")[-1].split("&")[0] if "youtube.com" in url_or_id or "youtu.be" in url_or_id else url_or_id
            endpoint = f"{self.base_url}/video"
            params = {'id': vid_id}
        else:
            url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
            endpoint = f"{self.base_url}/info"
            params = {'url': url}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success' or data.get('success') is True:
                            return data
                        else:
                            print(f"YT API info error: {data}")
        except Exception as e:
            print(f"Error fetching from YT API: {e}")
        
        return None

    async def search(self, query: str, message_id: int, video: bool = False):
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            endpoint = f"{self.base_url}/search"
            params = {'q': query, 'limit': 1}
        else:
            endpoint = f"{self.base_url}/search"
            params = {'query': query, 'limit': 1}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if (data.get('status') == 'success' or data.get('success') is True) and data.get('results'):
                            res = data['results'][0]
                            from Lily.helpers._dataclass import Media
                            from Lily.helpers import utils
                            duration_sec = int(res.get('duration', 0))
                            return Media(
                                id=res.get('id', ''),
                                title=res.get('title', ''),
                                duration=utils.format_duration(duration_sec),
                                duration_sec=duration_sec,
                                url=res.get('url', ''),
                                file_path=None,
                                message_id=message_id,
                                video=video
                            )
                        else:
                            print(f"YT API search error: {data}")
        except Exception as e:
            print(f"Error searching from YT API: {e}")
        
        # Fall back to yt.search if our API fails
        from Lily import yt
        return await yt.search(query, message_id, video=video)

    async def get_stream_url(self, vid_id: str, video: bool = False) -> str | None:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            endpoint = f"{self.base_url}/download"
            params = {'id': vid_id}
            if video:
                params['type'] = 'video'
            else:
                params['type'] = 'audio'
        else:
            endpoint = f"{self.base_url}/download"
            params = {'id': vid_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            data = await response.json()
                            if data.get('success') is True:
                                dl_info = data.get('download', {})
                                dl_url = dl_info.get('best_video_url') if video else dl_info.get('best_audio_url')
                                if not dl_url:
                                    dl_url = dl_info.get('best_video_url') or dl_info.get('url')
                                return dl_url
        except Exception as e:
            print(f"YT API: Error getting stream URL: {e}")
        return None

    async def playlist(self, limit: int, mention: str, url: str, video: bool = False):
        from Lily import yt
        return await yt.playlist(limit, mention, url, video)

    async def download(self, vid_id: str, video: bool = False):
        from Lily import yt
        return await yt.download(vid_id, video=video)
