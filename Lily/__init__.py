# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
#LILY CODER

import time
import logging
import static_ffmpeg
static_ffmpeg.add_paths()
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


__version__ = "3.0.1"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from Lily.core.bot import Bot
app = Bot()

from Lily.core.dir import ensure_dirs
ensure_dirs()

from Lily.core.userbot import Userbot
userbot = Userbot()

from Lily.core.mongo import MongoDB
db = MongoDB()

from Lily.core.lang import Language
from Lily.core.telegram import Telegram
from Lily.core.youtube import YouTube
from Lily.core.xbit import XBitAPI
from Lily.core.nexgen import NexGenAPI
from Lily.core.yt_api import YTAPI
from Lily.core.aruyt import AruYTAPI
tg = Telegram()
yt = YouTube()
xbit = XBitAPI()
nexgen = NexGenAPI()
yt_api = YTAPI()
aruyt = AruYTAPI()

from Lily.helpers import Queue
queue = Queue()

# Now import TgCall last so all dependencies are initialized
from Lily.core.calls import TgCall
anon = TgCall()


async def stop() -> None:
    logger.info("Stopping...")
    for task in tasks:
        task.cancel()
        try:
            await task
        except:
            pass

    await app.exit()
    await userbot.exit()
    await db.close()

    logger.info("Stopped.\n")
