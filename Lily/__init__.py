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
    format="[%(asctime)s - %(levelname)s - %(name)s: %(message)s]",
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

# Monkeypatch pyrogram to disable link previews globally
import inspect
import pyrogram

orig_send_message = pyrogram.Client.send_message
sig_send_message = inspect.signature(orig_send_message)

async def patched_send_message(self, *args, **kwargs):
    bound = sig_send_message.bind(self, *args, **kwargs)
    bound.apply_defaults()
    if "link_preview_options" in sig_send_message.parameters:
        bound.arguments["link_preview_options"] = pyrogram.types.LinkPreviewOptions(is_disabled=True)
    if "disable_web_page_preview" in sig_send_message.parameters:
        bound.arguments["disable_web_page_preview"] = True
    return await orig_send_message(*bound.args, **bound.kwargs)

orig_edit_message_text = pyrogram.Client.edit_message_text
sig_edit_message_text = inspect.signature(orig_edit_message_text)

async def patched_edit_message_text(self, *args, **kwargs):
    bound = sig_edit_message_text.bind(self, *args, **kwargs)
    bound.apply_defaults()
    if "link_preview_options" in sig_edit_message_text.parameters:
        bound.arguments["link_preview_options"] = pyrogram.types.LinkPreviewOptions(is_disabled=True)
    if "disable_web_page_preview" in sig_edit_message_text.parameters:
        bound.arguments["disable_web_page_preview"] = True
    return await orig_edit_message_text(*bound.args, **bound.kwargs)

pyrogram.Client.send_message = patched_send_message
pyrogram.Client.edit_message_text = patched_edit_message_text

from Lily.core.bot import Bot
app = Bot()

from Lily.core.dir import ensure_dirs
ensure_dirs()

from Lily.core.userbot import Userbot
userbot = Userbot()

from Lily.core.mongo import MongoDB
db = MongoDB()

from Lily.core.lang import Language
lang = Language()

from Lily.core.telegram import Telegram
tg = Telegram()

from Lily.core.youtube import YouTube
yt = YouTube()

from Lily.core.xbit import XBitAPI
xbit = XBitAPI()

from Lily.core.nexgen import NexGenAPI
nexgen = NexGenAPI()

from Lily.core.yt_api import YTAPI
yt_api = YTAPI()

from Lily.core.aruyt import AruYTAPI
aruyt = AruYTAPI()

from Lily.helpers import Queue
queue = Queue()

# Lazy import anon to avoid circular imports
_anon = None

def __getattr__(name):
    if name == "anon":
        global _anon
        if _anon is None:
            from Lily.core.calls import TgCall
            _anon = TgCall()
        return _anon
    raise AttributeError(f"module {__name__} has no attribute {name}")


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
