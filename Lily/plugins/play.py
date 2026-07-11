# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic

from pathlib import Path
import asyncio
import random
import os

from pyrogram import filters, types

from Lily import anon, app, config, db, lang, queue, tg, yt, xbit, nexgen, yt_api, aruyt
from Lily.helpers import buttons, utils, Track, Media
from Lily.helpers._play import checkUB


def playlist_to_queue(chat_id: int, tracks: list, user_id: int = None) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        if user_id:
            track.user_id = user_id
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text


async def background_stream(file: Media | Track, video: bool):
    """Prepare a queued item in the background so it's ready when its turn comes.

    Strategy:
      1. Try to resolve a live stream URL first (fast to start when played).
      2. Also download the file to disk in the background so playback can fall
         back to a local file without any network fetch at play time.
    Both are fire-and-forget; the queue item is mutated in place when ready.
    """
    try:
        if not file.file_path:
            # Pre-download the file so playback is instant & resilient.
            # Live YouTube stream URLs are IP/region-locked and cause
            # NoAudioSourceFound / 403, so we always play from a local file.
            exts = ["mp4"] if video else ["mp3", "webm"]
            for ext in exts:
                fname = f"downloads/{file.id}.{ext}"
                if os.path.exists(fname) and os.path.getsize(fname) > 0:
                    file.file_path = fname
                    print(f"Background cached file already present: {file.id} -> {fname}")
                    break
            if not file.file_path:
                local = await yt.download(file.id, video=video)
                if local:
                    file.file_path = local
                    print(f"Background download complete: {file.id} -> {local}")
                else:
                    print(f"Background preparation failed for {file.id} (will retry on play)")
    except Exception as e:
        print(f"Background stream error: {e}")


ARTISTS = {
    "arijit singh", "neha kakkar", "jubin nautiyal", "shreya ghoshal", "atif aslam", 
    "kk", "sonu nigam", "lata mangeshkar", "kishore kumar", "diljit dosanjh", 
    "badshah", "raftaar", "yo yo honey singh", "king", "mc stan", "sidhu moose wala", 
    "karan aujla", "ap dhillon", "darshan raval", "armaan malik", "alka yagnik", 
    "udit narayan", "kumar sanu", "sachin jigar", "pritam", "ar rahman", 
    "tanishk bagchi", "vishal shekhar", "mithoon", "anuv jain", "local train",
    "charlie puth", "ed sheeran", "taylor swift", "justin bieber", "selena gomez", 
    "drake", "eminem", "the weeknd", "bruno mars", "coldplay", "alan walker", 
    "marshmello", "dj snake", "david guetta", "dualipa", "billie eilish", 
    "ariana grande", "shakira", "rihanna", "post malone", "shawn mendes", 
    "camila cabello", "tony kakkar", "tulsi kumar", "asees kaur", "dhvani bhanushali",
    "guru randhawa", "jass manak", "hardy sandhu", "b praak", "jaani", "vishal mishra",
    "pawandeep rajan", "arunita kanjilal", "shekhar ravjiani", "vishal dadlani",
    "amit trivedi", "himesh reshammiya", "shankar mahadevan", "ehsaan", "loy",
    "shankar ehsaan loy", "salim sulaiman", "sajid wajid", "meet bros", "yo yo",
    "sia", "arijit", "shreya", "jubin", "sonu", "atif", "armaan", "darshan", "sunidhi",
    "sunidhi chauhan", "anirudh", "anirudh ravichander", "sid sriram", "sid", "sriram",
    "devi sri prasad", "dsp", "harrdy sandhu", "honey singh", "neha", "tony", "shekhar",
    "vishal", "diljit", "sidhu", "moosewala", "shubh", "rahman", "tanishk", "bagchi",
    "manak", "praak", "jasleen royal", "jasleen", "trivedi", "divine", "emiway",
    "emiway bantai", "krsna", "seedhe maut", "fotty seven", "dino james"
}

VIDEO_TERMS = {
    "official", "video", "audio", "lyric", "lyrics", "lyrical", "song", "songs", 
    "full", "hd", "4k", "remix", "cover", "lofi", "reverb", "slowed", "8d", 
    "karaoke", "music", "original", "version", "female", "male", "reprise", 
    "clean", "explicit", "prod", "by", "ft", "feat", "featuring", "presents", 
    "mp3", "download", "latest", "new", "trending", "best", "hits", "classic", 
    "pop", "rock", "rap", "hiphop", "bollywood", "punjabi", "hindi", "english",
    "series", "yrf", "t-series", "sony", "zeemusic", "speed records", "geet mp3"
}

@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce", "anyone", "anyoneplay"])
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
    sent = await m.reply_text(m.lang["play_searching"])
    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    # Handle "anyone" command specifically
    if m.command[0].lower() in ["anyone", "anyoneplay"]:
        if len(m.command) < 2:
            return await sent.edit_text(m.lang["play_usage"])
        
        query = " ".join(m.command[1:])
        
        # Search for the requested song
        file = await yt_api.search(query, sent.id, video=video)
        if not file and config.XBIT_API_TOKEN:
            file = await xbit.search(query, sent.id, video=video)
        if not file and config.NEXGENBOTS_API_TOKEN:
            file = await nexgen.search(query, sent.id, video=video)
        if not file:
            file = await yt.search(query, sent.id, video=video)
        
        if not file:
            return await sent.edit_text(m.lang["play_not_found"].format(config.SUPPORT_CHAT))
        
        file.user = mention
        file.user_id = m.from_user.id
        file.message_id = sent.id
        
        # Add to queue
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
                # Start background stream extraction for queued item
                asyncio.create_task(background_stream(file, video))
                return
        
        # If force is False and queue is empty or not playing, play immediately
        if position == 0 and not await db.get_call(m.chat.id):
            if not file.file_path:
                # Always download a local file for playback (no live stream).
                exts = ["mp4"] if video else ["mp3", "webm"]
                for ext in exts:
                    fname = f"downloads/{file.id}.{ext}"
                    if Path(fname).exists() and Path(fname).stat().st_size > 0:
                        file.file_path = fname
                        break

                if not file.file_path:
                    await sent.edit_text(m.lang["play_downloading"])
                    file.file_path = await yt.download(file.id, video=video)

                # Verify local file
                if file.file_path and not (file.file_path.startswith("http://") or file.file_path.startswith("https://")):
                    if not Path(file.file_path).exists() or Path(file.file_path).stat().st_size == 0:
                        return await sent.edit_text(m.lang["error_no_file"].format(config.SUPPORT_CHAT))

            await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
            return

    # Original play command handling (for non-anyone commands)
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
            file = await yt_api.search(url, sent.id, video=video)
            if not file and config.XBIT_API_TOKEN:
                file = await xbit.search(url, sent.id, video=video)
            if not file and config.NEXGENBOTS_API_TOKEN:
                file = await nexgen.search(url, sent.id, video=video)
            if not file:
                file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt_api.search(query, sent.id, video=video)
        if not file and config.XBIT_API_TOKEN:
            file = await xbit.search(query, sent.id, video=video)
        if not file and config.NEXGENBOTS_API_TOKEN:
            file = await nexgen.search(query, sent.id, video=video)
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
            # Start background stream extraction for queued item
            asyncio.create_task(background_stream(file, video))
            
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks, m.from_user.id)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    if not file.file_path:
        # Always download a local file for playback (no live stream).
        exts = ["mp4"] if video else ["mp3", "webm"]
        for ext in exts:
            fname = f"downloads/{file.id}.{ext}"
            if Path(fname).exists() and Path(fname).stat().st_size > 0:
                file.file_path = fname
                break

        if not file.file_path:
            await sent.edit_text(m.lang["play_downloading"])
            file.file_path = await yt.download(file.id, video=video)

        # Verify local file
        if file.file_path and not (file.file_path.startswith("http://") or file.file_path.startswith("https://")):
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
