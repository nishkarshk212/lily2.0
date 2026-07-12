#LILY CODER
from os import getenv
from dotenv import load_dotenv

load_dotenv()

def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0)."""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError(f"invalid truth value {val!r}")


def _ensure_scheme(url: str) -> str:
    """Ensure a URL carries an http(s) scheme.

    aiohttp raises ``InvalidUrlClientError`` on schemeless hosts (e.g.
    ``youtube-api-music-production-824b.up.railway.app/play/audio``), so the
    Railway downloader crashed before any request was sent. Normalise here.
    """
    if not url:
        return url
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url

class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", "17596251"))
        self.API_HASH = getenv("API_HASH", "e58343b4c0193e293e391daf97603fcd")

        self.BOT_TOKEN = getenv("BOT_TOKEN", "Apna Bot Token")
        self.MONGO_URL = getenv("MONGO_URL", "Apna Mongo Db Dalo")

        self.LOGGER_ID = int(getenv("LOGGER_ID", "Apna Log Group Id Dalo"))
        self.OWNER_ID = int(getenv("OWNER_ID", "Owner I'd dalo"))
        
        self.SESSION1 = getenv("SESSION", "Apna String Dalo")
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/Tele_212_bots")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/titanic_network")

        # Parse boolean configs correctly
        try:
            self.AUTO_END: bool = strtobool(getenv("AUTO_END", "false"))
        except ValueError:
            self.AUTO_END: bool = False
            
        try:
            self.AUTO_LEAVE: bool = strtobool(getenv("AUTO_LEAVE", "false"))
        except ValueError:
            self.AUTO_LEAVE: bool = False
            
        try:
            self.VIDEO_PLAY: bool = strtobool(getenv("VIDEO_PLAY", "true"))
        except ValueError:
            self.VIDEO_PLAY: bool = True

        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", "50"))
        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", "5400"))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", "20"))
        self.COOKIES_DATA = getenv("COOKIES_DATA", "")
        self.COOKIES_URL = [
            url for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg")
        self.PING_IMG = getenv("PING_IMG", "https://files.catbox.moe/haagg2.png")
        self.START_IMG = [
            url.strip(" `\"'") 
            for url in getenv("START_IMG", "https://i.ibb.co/dwSr1BCH/071045e1b930a364060e7f853a6394b8.jpg https://i.ibb.co/QjxJJq4z/a543640d2cae1726345278d761180958.jpg https://i.ibb.co/VcFwYZj0/c94b8f6d7917e218e2494ef8dda9873c.jpg").replace("`", " ").split()
            if url.strip(" `\"'")
        ]

        self.XBIT_API_TOKEN = getenv("XBIT_API_TOKEN") or getenv("XBIT_API_KEY") or getenv("YT_API_KEY")
        self.XBIT_API_URL = getenv("XBIT_API_URL") or getenv("YTPROXY_URL") or "https://tgapi.xbitcode.com"
        self.NEXGENBOTS_API_TOKEN = getenv("NEXGENBOTS_API_TOKEN")
        self.NEXGENBOTS_API_URL = getenv("NEXGENBOTS_API_URL", "https://pvtz.nexgenbots.xyz")
        self.VIDEO_API_URL = getenv("VIDEO_API_URL", "https://pvtz.nexgenbots.xyz")
        self.YT_API_BASE_URL = _ensure_scheme(
            getenv("YT_API_BASE_URL") or getenv("RAILWAY_YT_API_URL")
            or "https://youtube-api-music-production-824b.up.railway.app"
        )
        self.YT_API_KEY = getenv("YT_API_KEY") or getenv("RAILWAY_YT_API_KEY") or "SLtWox3TFKKHuMySdvz_4y2Ju3NlSHYk"
        self.SHRUTI_API_URL = getenv("SHRUTI_API_URL", "https://api.shrutibots.site")
        self.SHRUTI_API_KEY = getenv("SHRUTI_API_KEY")
        self.ARUYT_API_KEY = getenv("ARUYT_API_KEY", "ARU-4gjQEadsxdoVV0sJ51fHTbmK")
        self.ARUYT_API_URL = getenv("ARUYT_API_URL", "https://aruyt-production.up.railway.app")
        self.GIT_REPO = getenv("GIT_REPO", "https://github.com/nishkarshk212/Telegram_music")

        # ── YouTube source priority ──────────────────────────────────────────
        # Order in which Lily tries to obtain a playable stream (live) and a
        # downloadable file (background/cache). First source that yields a result
        # wins. Valid keys:
        #   yt_api  → Railway-hosted YouTube API (/download, /play/audio, /video)
        #   xbit    → xBit API
        #   aruyt   → AruYT API (currently offline / returns 404 — safe to drop)
        #   nexgen  → NexGenBots API
        #   local   → local yt-dlp (uses COOKIES_DATA + Node 24 for n-sig solving)
        # Set via PLAY_PRIORITY (comma/space separated).
        #
        # DEFAULT LEADS WITH `local`: as of 2026-07, YouTube bot-blocks the
        # Railway/server IP ("Sign in to confirm you're a bot"), so the local
        # yt-dlp path (with COOKIES_DATA + Node >= 23.5) is the reliable one.
        # Reorder to prefer hosted APIs, e.g. "yt_api,local,xbit".
        _priority_raw = getenv("PLAY_PRIORITY", "local,yt_api,xbit,aruyt,nexgen")
        _priority = [p.strip().lower() for p in _priority_raw.replace(",", " ").split() if p.strip()]
        self.PLAY_PRIORITY = _priority or ["local", "yt_api", "xbit", "aruyt", "nexgen"]

        # Return the sublist of priority entries that are actually configured
        # (keys with a configured API token/key). "local" is always available.
        def _enabled(priority_list=None):
            priority_list = priority_list or self.PLAY_PRIORITY
            enabled = []
            for key in priority_list:
                if key == "local":
                    enabled.append(key)
                elif key == "yt_api" and self.YT_API_BASE_URL and self.YT_API_KEY:
                    enabled.append(key)
                elif key == "xbit" and self.XBIT_API_TOKEN:
                    enabled.append(key)
                elif key == "aruyt" and self.ARUYT_API_KEY:
                    enabled.append(key)
                elif key == "nexgen" and self.NEXGENBOTS_API_TOKEN:
                    enabled.append(key)
            return enabled or ["local"]
        self._play_priority_enabled = _enabled

    def check(self):
        missing = []
        if not self.API_ID: missing.append("API_ID")
        if not self.API_HASH: missing.append("API_HASH")
        if not self.BOT_TOKEN: missing.append("BOT_TOKEN")
        if not self.MONGO_URL or "Apna Mongo" in self.MONGO_URL: missing.append("MONGO_URL")
        if not self.OWNER_ID: missing.append("OWNER_ID")
        if not self.SESSION1 or "Apna String" in self.SESSION1: missing.append("SESSION")
        
        if missing:
            raise SystemExit(f"Missing required environment variables in .env: {', '.join(missing)}")
