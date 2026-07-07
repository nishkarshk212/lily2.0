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
                            return Media(
                                id=res.get('id', ''),
                                title=res.get('title', ''),
                                duration=str(int(res.get('duration', 0))),
                                duration_sec=int(res.get('duration', 0)),
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

    async def playlist(self, limit: int, mention: str, url: str, video: bool = False):
        from Lily import yt
        return await yt.playlist(limit, mention, url, video)

    async def download(self, vid_id: str, video: bool = False):
        path = f"downloads/{vid_id}.{'mp4' if video else 'webm'}"
        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(path):
            print(f"YT API: File already exists at {path}")
            return path

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
            url = f"https://www.youtube.com/watch?v={vid_id}"
            endpoint = f"{self.base_url}/download"
            params = {'url': url}
        
        try:
            print(f"YT API: Downloading {vid_id} from {endpoint}")
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, headers=headers, timeout=300) as response:
                    if response.status == 200:
                        # First check if it's a JSON response containing stream URL
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            data = await response.json()
                            if data.get('success') is True:
                                dl_info = data.get('download', {})
                                dl_url = dl_info.get('best_video_url') if video else dl_info.get('best_audio_url')
                                if not dl_url:
                                    dl_url = dl_info.get('best_video_url') or dl_info.get('url')
                                
                                if dl_url:
                                    print(f"YT API: Streaming download from {dl_url}")
                                    async with session.get(dl_url, timeout=300) as dl_response:
                                        if dl_response.status == 200:
                                            with open(path, "wb") as f:
                                                async for chunk in dl_response.content.iter_chunked(1024 * 1024):
                                                    f.write(chunk)
                                        else:
                                            print(f"YT API: Streaming failed with status {dl_response.status}")
                                            return None
                                else:
                                    print(f"YT API: No stream URL found in JSON response")
                                    return None
                            else:
                                print(f"YT API download error (JSON): {data}")
                                return None
                        else:
                            with open(path, "wb") as f:
                                async for chunk in response.content.iter_chunked(1024 * 1024):
                                    f.write(chunk)
                        
                        if os.path.exists(path) and os.path.getsize(path) > 1024:
                            if not video:
                                # Convert webm/mp4 to mp3 for compatibility
                                mp3_path = f"downloads/{vid_id}.mp3"
                                print(f"YT API: Converting {path} to {mp3_path}")
                                subprocess.run(['ffmpeg', '-i', path, '-codec:a', 'libmp3lame', '-qscale:a', '2', mp3_path, '-y'], check=True, capture_output=True)
                                try:
                                    os.remove(path)
                                except:
                                    pass
                                path = mp3_path
                            print(f"YT API: Download successful, returning {path}")
                            return path
                        else:
                            print(f"YT API: Downloaded file too small or missing, size: {os.path.getsize(path) if os.path.exists(path) else 0}")
                    else:
                        print(f"YT API: Download failed with status {response.status}")
        except Exception as e:
            print(f"YT API: Error downloading: {e}")
        
        print(f"YT API: Falling back to other APIs for {vid_id}...")
        from Lily import nexgen, xbit, yt
        nexgen_res = await nexgen.download(vid_id, video=video)
        if nexgen_res:
            return nexgen_res
        xbit_res = await xbit.download(vid_id, video=video)
        if xbit_res:
            return xbit_res
        return await yt.download(vid_id, video=video)
