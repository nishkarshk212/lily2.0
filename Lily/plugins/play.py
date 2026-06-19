# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
#LILY CODER

from pathlib import Path
import asyncio

from pyrogram import filters, types

from Lily import app, lang
from Lily.helpers._play import checkUB

# These will be imported lazily inside functions
config = None
db = None
queue = None
tg = None
yt = None
xbit = None
nexgen = None
yt_api = None
aruyt = None
buttons = None
utils = None
Track = None
Media = None
anon = None

def _import_helpers():
    """Lazy import helper modules"""
    global config, db, queue, tg, yt, xbit, nexgen, yt_api, aruyt, buttons, utils, Track, Media, anon
    if config is None:
        from Lily import (
            config as _config,
            db as _db,
            queue as _queue,
            tg as _tg,
            yt as _yt,
            xbit as _xbit,
            nexgen as _nexgen,
            yt_api as _yt_api,
            aruyt as _aruyt,
            anon as _anon
        )
        from Lily.helpers import buttons as _buttons, utils as _utils, Track as _Track, Media as _Media
        config = _config
        db = _db
        queue = _queue
        tg = _tg
        yt = _yt
        xbit = _xbit
        nexgen = _nexgen
        yt_api = _yt_api
        aruyt = _aruyt
        buttons = _buttons
        utils = _utils
        Track = _Track
        Media = _Media
        anon = _anon


def playlist_to_queue(chat_id: int, tracks: list, user_id: int = None) -> str:
    _import_helpers()
    text = "<blockquote expandable>"
    for track in tracks:
        if user_id:
            track.user_id = user_id
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text

async def background_download(file, video: bool):
    _import_helpers()
    try:
        if not file.file_path:
            fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
            if Path(fname).exists():
                file.file_path = fname
            else:
                # Check cache first
                cache = await db.get_media_cache(file.id)
                if cache:
                    file.file_path = cache.get("video_url") if video else cache.get("audio_url")
                
                if not file.file_path:
                    if config.ARUYT_API_KEY:
                        print(f"Starting background download for {file.id} using AruYT API...")
                        file.file_path = await aruyt.download(file.id, video=video)
                    if not file.file_path and config.XBIT_API_TOKEN:
                        print(f"Starting background download for {file.id} using XBit API...")
                        file.file_path = await xbit.download(file.id, video=video)
                    if not file.file_path and config.NEXGENBOTS_API_TOKEN:
                        print(f"Starting background download for {file.id} using NexGen API...")
                        file.file_path = await nexgen.download(file.id, video=video)
                    if not file.file_path:
                        print(f"Starting background download for {file.id} using YT API...")
                        file.file_path = await yt_api.download(file.id, video=video)
                    if not file.file_path:
                        print(f"Starting background download for {file.id} using ytdlp...")
                        file.file_path = await yt.download(file.id, video=video)
                    if file.file_path:
                        print(f"Background download successful: {file.file_path}")
                    else:
                        print(f"Background download failed for {file.id}")
                    # Save to cache if it's a URL
                    if file.file_path and (file.file_path.startswith("http") or file.file_path.startswith("https")):
                        cache_data = {
                            "title": file.title,
                            "duration": file.duration,
                            "duration_sec": file.duration_sec,
                            ("video_url" if video else "audio_url"): file.file_path
                        }
                        await db.save_media_cache(file.id, cache_data)
    except Exception as e:
        print(f"Background download error: {e}")

@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    _import_helpers()
    sent = await m.reply_text(m.lang["play_searching"])
    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    if url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            if config.XBIT_API_TOKEN:
                tracks = await xbit.playlist(config.PLAYLIST_LIMIT, mention, url, video)
            if not tracks and config.NEXGENBOTS_API_TOKEN:
                tracks = await nexgen.playlist(config.PLAYLIST_LIMIT, mention, url, video)
            if not tracks:
                tracks = await yt_api.playlist(config.PLAYLIST_LIMIT, mention, url, video)
            if not tracks:
                tracks = await yt.playlist(
                    config.PLAYLIST_LIMIT, mention, url, video
                )

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            if config.XBIT_API_TOKEN:
                file = await xbit.search(url, sent.id, video=video)
            if not file and config.NEXGENBOTS_API_TOKEN:
                file = await nexgen.search(url, sent.id, video=video)
            if not file:
                file = await yt_api.search(url, sent.id, video=video)
            if not file:
                file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        if config.XBIT_API_TOKEN:
            file = await xbit.search(query, sent.id, video=video)
        if not file and config.NEXGENBOTS_API_TOKEN:
            file = await nexgen.search(query, sent.id, video=video)
        if not file:
            file = await yt_api.search(query, sent.id, video=video)
        if not file:
            file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, file.title, file.duration)

    file.user = mention
    file.user_id = m.from_user.id
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(
                    position,
                    file.url,
                    file.title,
                    file.duration,
                    m.from_user.mention,
                ),
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )
            # Start background download for queued item
            asyncio.create_task(background_download(file, video))
            
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks, m.from_user.id)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            # Check cache first
            cache = await db.get_media_cache(file.id)
            if cache:
                file.file_path = cache.get("video_url") if video else cache.get("audio_url")
            
            if not file.file_path:
                await sent.edit_text(m.lang["play_downloading"])
                if config.ARUYT_API_KEY:
                    file.file_path = await aruyt.download(file.id, video=video)
                if not file.file_path and config.XBIT_API_TOKEN:
                    file.file_path = await xbit.download(file.id, video=video)
                if not file.file_path and config.NEXGENBOTS_API_TOKEN:
                    file.file_path = await nexgen.download(file.id, video=video)
                if not file.file_path:
                    file.file_path = await yt_api.download(file.id, video=video)
                if not file.file_path:
                    file.file_path = await yt.download(file.id, video=video)
                # Save to cache if it's a URL
                if file.file_path and (file.file_path.startswith("http") or file.file_path.startswith("https")):
                    cache_data = {
                        "title": file.title,
                        "duration": file.duration,
                        "duration_sec": file.duration_sec,
                        ("video_url" if video else "audio_url"): file.file_path
                    }
                    await db.save_media_cache(file.id, cache_data)
        
        # Verify local file
        if file.file_path and not (file.file_path.startswith("http") or file.file_path.startswith("https")):
            if not Path(file.file_path).exists() or Path(file.file_path).stat().st_size == 0:
                return await sent.edit_text(m.lang["error_no_file"].format(config.SUPPORT_CHAT))

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks, m.from_user.id)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )
