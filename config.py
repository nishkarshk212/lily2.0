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

        self.XBIT_API_TOKEN = getenv("XBIT_API_TOKEN") or getenv("XBIT_API_KEY")
        self.XBIT_API_URL = getenv("XBIT_API_URL", "https://tgapi.xbitcode.com")
        self.NEXGENBOTS_API_TOKEN = getenv("NEXGENBOTS_API_TOKEN")
        self.NEXGENBOTS_API_URL = getenv("NEXGENBOTS_API_URL", "https://pvtz.nexgenbots.xyz")
        self.VIDEO_API_URL = getenv("VIDEO_API_URL", "https://pvtz.nexgenbots.xyz")
        self.YT_API_BASE_URL = getenv("YT_API_BASE_URL", "https://yt-api-two-plum.vercel.app")
        self.YT_API_KEY = getenv("YT_API_KEY")
        self.ARUYT_API_KEY = getenv("ARUYT_API_KEY", "ARU-4gjQEadsxdoVV0sJ51fHTbmK")
        self.ARUYT_API_URL = getenv("ARUYT_API_URL", "https://aruyt-production.up.railway.app")
        self.GIT_REPO = getenv("GIT_REPO", "https://github.com/nishkarshk212/Telegram_music")

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
