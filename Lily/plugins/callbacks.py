# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


import re

from pyrogram import filters, types

from Lily import anon, app, db, lang, queue, tg, yt, xbit, nexgen, yt_api
from Lily.helpers import admin_check, buttons, can_manage_vc, can_skip, extra_inline
from Lily.helpers._dataclass import Track, Media



@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
async def cancel_dl(_, query: types.CallbackQuery):
    await query.answer()
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()
    action, chat_id = args[1], int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention
    user_id = query.from_user.id

    if not await db.get_call(chat_id):
        return await query.answer(query.lang["not_playing"], show_alert=True)

    if action == "status":
        return await query.answer()

    # Permission check
    is_admin = False
    if user_id in app.sudoers or await db.is_auth(chat_id, user_id):
        is_admin = True
    else:
        admins = await db.get_admins(chat_id)
        if user_id in admins:
            is_admin = True

    if not is_admin:
        if action in ["skip", "replay"]:
            current = queue.get_current(chat_id)
            if not current or current.user_id != user_id:
                return await query.answer(query.lang["user_no_perms"], show_alert=True)
        else:
            return await query.answer(query.lang["user_no_perms"], show_alert=True)

    await query.answer(query.lang["processing"], show_alert=True)

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer(
                query.lang["play_already_paused"], show_alert=True
            )
        await anon.pause(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["paused"], False)
            )
        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        if await db.playing(chat_id):
            return await query.answer(query.lang["play_not_paused"], show_alert=True)
        await anon.resume(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["playing"], True)
            )
        reply = query.lang["play_resumed"].format(user)

    elif action == "skip":
        await anon.play_next(chat_id)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await query.edit_message_text(query.lang["play_expired"])

        m_id = queue.get_current(chat_id).message_id
        queue.force_add(chat_id, media, remove=pos)
        try:
            await app.delete_messages(
                chat_id=chat_id, message_ids=[m_id, media.message_id], revoke=True
            )
            media.message_id = None
        except:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])
        if not media.file_path:
            # Check cache
            cache = await db.get_media_cache(media.id)
            if cache:
                media.file_path = cache.get("video_url") if media.video else cache.get("audio_url")
            
            if not media.file_path:
                media.file_path = await xbit.download(media.id, video=media.video)
                # Save to cache if it's a URL
                if media.file_path and (media.file_path.startswith("http") or media.file_path.startswith("https")):
                    cache_data = {
                        "title": media.title,
                        "duration": media.duration,
                        "duration_sec": media.duration_sec,
                        ("video_url" if media.video else "audio_url"): media.file_path
                    }
                    await db.save_media_cache(media.id, cache_data)
        
        media.message_id = msg.id
        return await anon.play_media(chat_id, msg, media)

    elif action == "replay":
        media = queue.get_current(chat_id)
        media.user = user
        await anon.replay(chat_id)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await anon.stop(chat_id)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    try:
        if action in ["skip", "replay", "stop"]:
            await query.message.reply_text(reply, quote=False)
            await query.message.delete()
        else:
            mtext = re.sub(
                r"\n\n<blockquote>.*?</blockquote>",
                "",
                query.message.caption.html or query.message.text.html,
                flags=re.DOTALL,
            )
            keyboard = buttons.controls(
                chat_id, status=status if action != "resume" else None
            )
        await query.edit_message_text(
            f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
        )
    except:
        pass


@app.on_callback_query(filters.regex("help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    data = query.data.split()
    if len(data) == 1:
        return await query.answer(url=f"https://t.me/{app.username}?start=help")

    if data[1] == "back":
        return await query.edit_message_text(
            text=query.lang["help_menu"], reply_markup=buttons.help_markup(query.lang)
        )
    elif data[1] == "close":
        try:
            await query.message.delete()
        except:
            pass
        try:
            await query.message.reply_to_message.delete()
        except:
            pass
        return

    help_key = f"help_{data[1]}"
    if help_key not in query.lang:
        return await query.answer(f"Help for '{data[1]}' not found.", show_alert=True)

    await query.edit_message_text(
        text=query.lang[help_key],
        reply_markup=buttons.help_markup(query.lang, True),
    )


@app.on_callback_query(filters.regex("settings") & ~app.bl_users)
@lang.language()
@admin_check
async def _settings_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()
    chat_id = query.message.chat.id
    if len(cmd) == 1:
        await query.answer(query.lang["processing"], show_alert=True)
        admin_only = await db.get_play_mode(chat_id)
        cmd_delete = await db.get_cmd_delete(chat_id)
        pmsg_delete = await db.get_playmsg_delete(chat_id)
        skip_mode = await db.get_skip_mode(chat_id)
        return await query.edit_message_text(
            text=query.lang["start_settings"].format(query.message.chat.title),
            reply_markup=extra_inline.settings_markup(
                query.lang, admin_only, cmd_delete, pmsg_delete, skip_mode, chat_id
            ),
        )

    await query.answer(query.lang["processing"], show_alert=True)
    _admin = await db.get_play_mode(chat_id)
    _delete = await db.get_cmd_delete(chat_id)
    _pmsg_delete = await db.get_playmsg_delete(chat_id)
    _skip = await db.get_skip_mode(chat_id)
    _language = await db.get_lang(chat_id)

    if cmd[1] == "delete":
        _delete = not _delete
        await db.set_cmd_delete(chat_id, _delete)
    elif cmd[1] == "play":
        await db.set_play_mode(chat_id, _admin)
        _admin = not _admin
    elif cmd[1] == "pmsg_delete":
        _pmsg_delete = not _pmsg_delete
        await db.set_playmsg_delete(chat_id, _pmsg_delete)
    elif cmd[1] == "skip":
        _skip = not _skip
        await db.set_skip_mode(chat_id, _skip)

    await query.edit_message_reply_markup(
        reply_markup=extra_inline.settings_markup(
            query.lang,
            _admin,
            _delete,
            _pmsg_delete,
            _skip,
            chat_id,
        )
    )


# ── Related Song Suggestions ──────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^add_related ") & ~app.bl_users)
@lang.language()
async def add_related_song(_, query: types.CallbackQuery):
    """When a user taps a related-song button, fetch it and add it to the queue."""
    await query.answer()
    parts = query.data.split()
    # Format: add_related <index> <chat_id> <user_id>
    if len(parts) < 4:
        return await query.answer("Invalid data.", show_alert=True)

    idx = int(parts[1])
    chat_id = int(parts[2])
    orig_user_id = int(parts[3])
    requester_id = query.from_user.id

    # Peek (don't consume) the stored related songs so multiple people can add
    related_songs = await db.peek_temp_data(f"related_songs:{chat_id}:{orig_user_id}")
    if not related_songs or idx >= len(related_songs):
        return await query.answer(
            "⚠️ Suggestions have expired or the index is invalid. Play a new song to get fresh suggestions.",
            show_alert=True,
        )

    song = related_songs[idx]
    title = song["title"]
    vid_id = song["id"]
    vid_url = song["url"]
    duration = song.get("duration", "N/A")
    duration_sec = song.get("duration_sec", 0)

    # Build a Media object for the queue
    from Lily import config
    media_obj = Media(
        id=vid_id,
        title=title,
        duration=duration,
        duration_sec=duration_sec,
        url=vid_url,
        file_path=None,
        message_id=query.message.id,
        user=query.from_user.mention,
        user_id=requester_id,
    )

    # Check queue limit
    if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
        return await query.answer(
            f"❌ Queue is full ({config.QUEUE_LIMIT} songs max).", show_alert=True
        )

    position = queue.add(chat_id, media_obj)

    # Update the suggestion message to show what was added
    try:
        original_text = query.message.text.html if query.message.text else ""
        new_text = original_text + f"\n\n✅ <b>Added to queue</b> (#{position}): <a href='{vid_url}'>{title}</a>"
        # Rebuild keyboard without the added button
        new_rows = []
        if query.message.reply_markup and query.message.reply_markup.inline_keyboard:
            for row in query.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data == query.data:
                        # Replace with a "✅ Added" indicator (disabled via answered)
                        new_rows.append([
                            types.InlineKeyboardButton(
                                text=f"✅ {btn.text.lstrip('➕ ♪🟢🟡🔵🟠🔴 ')} (added)",
                                callback_data="noop"
                            )
                        ])
                    else:
                        new_rows.append([btn])
        await query.edit_message_text(
            new_text,
            reply_markup=types.InlineKeyboardMarkup(new_rows) if new_rows else None,
        )
    except Exception:
        await query.answer(f"✅ Added to queue: {title}", show_alert=True)


@app.on_callback_query(filters.regex(r"^dismiss_related ") & ~app.bl_users)
@lang.language()
async def dismiss_related(_, query: types.CallbackQuery):
    """Delete the related-songs suggestion message."""
    await query.answer("Dismissed.")
    try:
        await query.message.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^more_related ") & ~app.bl_users)
async def more_related_callback(_, query: types.CallbackQuery):
    """Switch pages of suggested songs (cycles between Page 1 and Page 2)."""
    parts = query.data.split()
    # Format: more_related <page> <chat_id> <user_id>
    if len(parts) < 4:
        return await query.answer("Invalid data.", show_alert=True)

    page = int(parts[1])
    chat_id = int(parts[2])
    user_id = int(parts[3])

    related_songs = await db.peek_temp_data(f"related_songs:{chat_id}:{user_id}")
    if not related_songs:
        return await query.answer(
            "⚠️ Suggestions have expired. Play a new song to get fresh suggestions.",
            show_alert=True,
        )

    kb_rows = []
    # page == 1 -> show songs 3, 4, 5 (Page 2)
    # page == 0 -> show songs 0, 1, 2 (Page 1)
    start_idx = 3 if page == 1 else 0
    end_idx = min(start_idx + 3, len(related_songs))

    for i in range(start_idx, end_idx):
        song = related_songs[i]
        title_short = song["title"][:38] + ("…" if len(song["title"]) > 38 else "")
        kb_rows.append([
            types.InlineKeyboardButton(
                text=f"♪ {title_short}",
                callback_data=f"add_related {i} {chat_id} {user_id}"
            )
        ])

    # Add toggle button
    next_page = 0 if page == 1 else 1
    btn_text = "Back ↩️" if page == 1 else "More Songs ?"
    kb_rows.append([
        types.InlineKeyboardButton(
            text=btn_text,
            callback_data=f"more_related {next_page} {chat_id} {user_id}"
        )
    ])

    await query.answer()
    try:
        await query.edit_message_reply_markup(
            reply_markup=types.InlineKeyboardMarkup(kb_rows)
        )
    except Exception as e:
        print(f"more_related_callback edit error: {e}")


@app.on_callback_query(filters.regex(r"^noop$") & ~app.bl_users)
async def noop_callback(_, query: types.CallbackQuery):
    """No-operation callback for already-added song buttons."""
    await query.answer("Already added to queue.", show_alert=False)
