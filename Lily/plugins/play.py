# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic

from pathlib import Path
import asyncio
import random

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


async def background_download(file: Media | Track, video: bool):
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
                    if config.XBIT_API_TOKEN:
                        print(f"Starting background download for {file.id} using XBit API...")
                        file.file_path = await xbit.download(file.id, video=video)
                    if not file.file_path and config.ARUYT_API_KEY:
                        print(f"Starting background download for {file.id} using AruYT API...")
                        file.file_path = await aruyt.download(file.id, video=video)
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


def _detect_language(title: str) -> str:
    """
    Detect if a song title is Hindi/Bollywood or generic English.
    Returns 'hindi' for Devanagari script or common Bollywood keywords,
    otherwise returns 'english'.
    """
    import re
    # Devanagari Unicode block
    if re.search(r'[\u0900-\u097F]', title):
        return "hindi"
    hindi_keywords = [
        "hindi", "bollywood", "filmi", "gaana", "gana", "desi",
        "pyaar", "ishq", "mohabbat", "dil", "zindagi", "rang",
        "tere", "mera", "tera", "aaja", "sunle", "duniya",
        "dilwale", "jaan", "baarish", "raat", "sapna", "yaar",
        "shukriya", "khuda", "hawa", "aashiq", "pehli", "pal",
    ]
    title_lower = title.lower()
    for kw in hindi_keywords:
        if kw in title_lower:
            return "hindi"
    return "english"


async def get_related_songs(track, limit=6) -> list:
    """
    Get related/suggested songs different from the currently playing track.
    Language-aware: Hindi songs get Hindi suggestions, others get similar-genre results.
    Returns a list of up to `limit` dicts: {id, title, url, duration, duration_sec, lang}.
    """
    related = []
    current_id = getattr(track, "id", "")
    title = getattr(track, "title", "")
    lang_hint = _detect_language(title)

    # Language-aware search query
    if lang_hint == "hindi":
        query = f"{title} best hindi songs"
    else:
        query = f"songs like {title}"

    seen_ids = {current_id}  # deduplicate: skip the currently playing song

    # Primary: py_yt — fetch 12 so we have enough after dedup
    try:
        from py_yt import VideosSearch
        search = VideosSearch(query, limit=12)
        results = (await search.next()).get("result", [])
        for video in results:
            vid_id = video.get("id", "")
            if not vid_id or vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)
            raw_dur = video.get("duration", "0:00") or "0:00"
            parts = raw_dur.split(":")
            try:
                if len(parts) == 3:
                    dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    dur_sec = int(parts[0]) * 60 + int(parts[1])
                else:
                    dur_sec = int(parts[0])
            except Exception:
                dur_sec = 0
            related.append({
                "id": vid_id,
                "title": video.get("title", "Unknown"),
                "url": video.get("link", f"https://youtube.com/watch?v={vid_id}"),
                "duration": raw_dur,
                "duration_sec": dur_sec,
                "lang": lang_hint,
            })
            if len(related) >= limit:
                break
    except Exception as e:
        print(f"py_yt related search error: {e}")

    # Fallback: yt_api if py_yt gave nothing
    if not related:
        try:
            res = await yt_api.search(query, 0)
            if res and res.id not in seen_ids:
                related.append({
                    "id": res.id,
                    "title": res.title,
                    "url": res.url,
                    "duration": res.duration,
                    "duration_sec": res.duration_sec,
                    "lang": lang_hint,
                })
        except Exception as e:
            print(f"yt_api related search error: {e}")

    return related


# Colorful emoji dots cycled across suggestion buttons
_BTN_COLORS = ["🟢", "🟡", "🔵", "🟠", "🔴"]


async def send_related_suggestions(chat_id: int, user_id: int, track, sent_msg):
    """Fetch 6 language-aware related songs and send them as inline buttons with ♪ prefix and pagination."""
    try:
        related_songs = await get_related_songs(track, limit=6)
        if not related_songs:
            return

        # Store for callback retrieval
        await db.set_temp_data(f"related_songs:{chat_id}:{user_id}", related_songs)

        # One button per suggested song for Page 1 (indices 0, 1, 2)
        kb_rows = []
        for i in range(min(3, len(related_songs))):
            song = related_songs[i]
            title_short = song["title"][:38] + ("…" if len(song["title"]) > 38 else "")
            kb_rows.append([
                types.InlineKeyboardButton(
                    text=f"♪ {title_short}",
                    callback_data=f"add_related {i} {chat_id} {user_id}"
                )
            ])

        # Add More Songs button if there are more than 3 songs
        if len(related_songs) > 3:
            kb_rows.append([
                types.InlineKeyboardButton(
                    text="More Songs ?",
                    callback_data=f"more_related 1 {chat_id} {user_id}"
                )
            ])

        await app.send_message(
            chat_id=chat_id,
            text=(
                f"<b><a href='https://t.me/{app.username}'>{app.name}</a> ↬ Music</b>\n"
                f"<b>You May Like to Listen these tracks</b>\n\n"
                f"Choose a song below & I'll play it in this voice chat."
            ),
            reply_markup=types.InlineKeyboardMarkup(kb_rows),
        )
    except Exception as e:
        print(f"send_related_suggestions error: {e}")


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
        if config.XBIT_API_TOKEN:
            file = await xbit.search(query, sent.id, video=video)
        if not file and config.NEXGENBOTS_API_TOKEN:
            file = await nexgen.search(query, sent.id, video=video)
        if not file:
            file = await yt_api.search(query, sent.id, video=video)
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
                # Start background download for queued item
                asyncio.create_task(background_download(file, video))
                
                # Send related song suggestions
                asyncio.create_task(
                    send_related_suggestions(m.chat.id, m.from_user.id, file, sent)
                )
                
                return
        
        # If force is False and queue is empty or not playing, play immediately
        if position == 0 and not await db.get_call(m.chat.id):
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
                        if config.XBIT_API_TOKEN:
                            file.file_path = await xbit.download(file.id, video=video)
                        if not file.file_path and config.ARUYT_API_KEY:
                            file.file_path = await aruyt.download(file.id, video=video)
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
            
            # Send related song suggestions after playback starts
            asyncio.create_task(
                send_related_suggestions(m.chat.id, m.from_user.id, file, sent)
            )
            
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
            
            # Send related song suggestions
            asyncio.create_task(
                send_related_suggestions(m.chat.id, m.from_user.id, file, sent)
            )
            
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
                if config.XBIT_API_TOKEN:
                    file.file_path = await xbit.download(file.id, video=video)
                if not file.file_path and config.ARUYT_API_KEY:
                    file.file_path = await aruyt.download(file.id, video=video)
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
    # Send related song suggestions after playback starts
    asyncio.create_task(
        send_related_suggestions(m.chat.id, m.from_user.id, file, sent)
    )
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks, m.from_user.id)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )
