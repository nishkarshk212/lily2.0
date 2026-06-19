
import aiohttp
import os

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

    async def download(self, vid_id: str, video: bool = False):
        path = f"downloads/{vid_id}.{'mp4' if video else 'mp3'}"
        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(path):
            return path

        if self.api_key:
            url = f"{self.base_url}/download?api_key={self.api_key}&url=https://www.youtube.com/watch?v={vid_id}"
            if video:
                url += "&type=video"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=300) as response:
                        if response.status == 200:
                            with open(path, "wb") as f:
                                async for chunk in response.content.iter_chunked(1024 * 1024):
                                    f.write(chunk)
                            if os.path.exists(path) and os.path.getsize(path) > 1024:
                                return path
                        else:
                            print(f"AruYT download failed with status {response.status} for {vid_id}")
            except Exception as e:
                print(f"Error downloading from AruYT: {e}")
        
        print(f"Falling back to XBit API for {vid_id}...")
        from Lily import xbit
        return await xbit.download(vid_id, video=video)
