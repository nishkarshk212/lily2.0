# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


import re

from pyrogram import filters, types

from Lily import anon, app, db, lang, queue, tg, yt, xbit, nexgen, yt_api, aruyt
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
                import time
                cached_at = cache.get("cached_at", 0)
                if time.time() - cached_at < 10800:
                    media.file_path = cache.get("video_url") if media.video else cache.get("audio_url")
            
            if not media.file_path:
                media.file_path = await yt_api.download(media.id, video=media.video)
                # Save to cache if it's a URL
                if media.file_path and (media.file_path.startswith("http") or media.file_path.startswith("https")):
                    import time
                    cache_data = {
                        "title": media.title,
                        "duration": media.duration,
                        "duration_sec": media.duration_sec,
                        ("video_url" if media.video else "audio_url"): media.file_path,
                        "cached_at": time.time()
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
                chat_id,
                status=status if action != "resume" else None,
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
        promo_mode = await db.get_promo_mode(chat_id)
        return await query.edit_message_text(
            text=query.lang["start_settings"].format(query.message.chat.title),
            reply_markup=extra_inline.settings_markup(
                query.lang, admin_only, cmd_delete, pmsg_delete, skip_mode, promo_mode, chat_id
            ),
        )

    await query.answer(query.lang["processing"], show_alert=True)
    _admin = await db.get_play_mode(chat_id)
    _delete = await db.get_cmd_delete(chat_id)
    _pmsg_delete = await db.get_playmsg_delete(chat_id)
    _skip = await db.get_skip_mode(chat_id)
    _promo = await db.get_promo_mode(chat_id)
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
    elif cmd[1] == "promo":
        _promo = not _promo
        await db.set_promo_mode(chat_id, _promo)

    await query.edit_message_reply_markup(
        reply_markup=extra_inline.settings_markup(
            query.lang,
            _admin,
            _delete,
            _pmsg_delete,
            _skip,
            _promo,
            chat_id,
        )
    )
