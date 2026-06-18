# Lily Coder
import aiohttp

class YTAPI:
    def __init__(self):
        from Lily import config
        self.base_url = config.YT_API_BASE_URL

    async def get_info(self, url_or_id: str):
        url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
        endpoint = f"{self.base_url}/info"
        params = {'url': url}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success':
                            return data
        except Exception as e:
            print(f"Error fetching from YT API: {e}")
        
        return None

    async def search(self, query: str, message_id: int, video: bool = False):
        from py_youtube_search import YoutubeSearch
        try:
            results = YoutubeSearch(query, max_results=1).to_dict()
            if results:
                res = results[0]
                from Lily.helpers._dataclass import Media
                return Media(
                    id=res['id'],
                    title=res['title'],
                    duration=res['duration'],
                    duration_sec=0,  # We'll handle this later if needed
                    url=f"https://www.youtube.com{res['url_suffix']}",
                    file_path=None,
                    message_id=message_id,
                    video=video
                )
        except Exception as e:
            print(f"Error searching YouTube: {e}")
        return None

    async def playlist(self, limit: int, mention: str, url: str, video: bool = False):
        from Lily import yt
        return await yt.playlist(limit, mention, url, video)

    async def download(self, vid_id: str, video: bool = False):
        path = f"downloads/{vid_id}.{'mp4' if video else 'webm'}"
        import os
        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(path):
            return path

        url = f"https://www.youtube.com/watch?v={vid_id}"
        endpoint = f"{self.base_url}/download"
        params = {'url': url}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, timeout=300) as response:
                    if response.status == 200:
                        with open(path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                        if os.path.exists(path) and os.path.getsize(path) > 1024:
                            if not video:
                                # Convert webm to mp3 for compatibility
                                import subprocess
                                mp3_path = f"downloads/{vid_id}.mp3"
                                subprocess.run(['ffmpeg', '-i', path, '-codec:a', 'libmp3lame', '-qscale:a', '2', mp3_path, '-y'], check=True, capture_output=True)
                                os.remove(path)
                                path = mp3_path
                            return path
                        else:
                            print(f"Downloaded file is too small or missing for {vid_id}")
                    else:
                        print(f"YT API download failed with status {response.status} for {vid_id}")
        except Exception as e:
            print(f"Error downloading from YT API: {e}")
        
        print(f"Falling back to other APIs for {vid_id}...")
        from Lily import nexgen, xbit, yt
        nexgen_res = await nexgen.download(vid_id, video=video)
        if nexgen_res:
            return nexgen_res
        xbit_res = await xbit.download(vid_id, video=video)
        if xbit_res:
            return xbit_res
        return await yt.download(vid_id, video=video)
