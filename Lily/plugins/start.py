# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
#LILY CODER

import asyncio
import random
from pyrogram import enums, filters, types

from Lily import app, config, db, lang, logger
from Lily.helpers import buttons, utils, extra_inline


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    await m.reply_text(
        text=m.lang["help_menu"],
        reply_markup=buttons.help_markup(m.lang),
        quote=True,
    )


@app.on_message(filters.command(["start"]))
@lang.language()
async def start(_, message: types.Message):
    if message.from_user.id in app.bl_users and message.from_user.id not in db.notified:
        return await message.reply_text(message.lang["bl_user_notify"])

    if len(message.command) > 1 and message.command[1] == "help":
        return await _help(_, message)

    private = message.chat.type == enums.ChatType.PRIVATE
    _text = (
        message.lang["start_pm"].format(message.from_user.first_name, app.name)
        if private
        else message.lang["start_gp"].format(app.name)
    )

    key = buttons.start_key(message.lang, private)
    # Replace source button URL
    for row in key.inline_keyboard:
        for button in row:
            if button.text == message.lang["source"]:
                button.url = config.GIT_REPO

    # Try first with all buttons
    try:
        await message.reply_photo(
            photo=random.choice(config.START_IMG),
            caption=_text,
            reply_markup=key,
            quote=not private,
        )
    except Exception as e:
        logger.warning(f"Error sending start photo with full buttons: {e}")
        # Try filtering out ONLY the button(s) that have user_id set (the privacy-restricted one)
        filtered_keyboard = []
        for row in key.inline_keyboard:
            filtered_row = []
            for button in row:
                if not hasattr(button, "user_id") or not button.user_id:
                    filtered_row.append(button)
            if filtered_row:
                filtered_keyboard.append(filtered_row)
        filtered_key = types.InlineKeyboardMarkup(filtered_keyboard) if filtered_keyboard else None
        
        if filtered_key:
            try:
                await message.reply_photo(
                    photo=random.choice(config.START_IMG),
                    caption=_text,
                    reply_markup=filtered_key,
                    quote=not private,
                )
            except Exception as e2:
                    logger.warning(f"Error sending start photo with filtered buttons: {e2}")
                    try:
                        await message.reply_photo(
                            photo=random.choice(config.START_IMG),
                            caption=_text,
                            quote=not private,
                        )
                    except Exception as e3:
                        logger.warning(f"Error sending start photo without buttons: {e3}")
                        await message.reply_text(
                            text=_text,
                            quote=not private,
                        )
        else:
            try:
                await message.reply_photo(
                    photo=random.choice(config.START_IMG),
                    caption=_text,
                    quote=not private,
                )
            except Exception as e2:
                logger.warning(f"Error sending start photo without buttons: {e2}")
                await message.reply_text(
                    text=_text,
                    quote=not private,
                )

    if private:
        if await db.is_user(message.from_user.id):
            return
        await utils.send_log(message)
        await db.add_user(message.from_user.id)
    else:
        if await db.is_chat(message.chat.id):
            return
        await utils.send_log(message, True)
        await db.add_chat(message.chat.id)


@app.on_message(filters.command(["playmode", "settings"]) & filters.group & ~app.bl_users)
@lang.language()
async def settings(_, message: types.Message):
    admin_only = await db.get_play_mode(message.chat.id)
    cmd_delete = await db.get_cmd_delete(message.chat.id)
    pmsg_delete = await db.get_playmsg_delete(message.chat.id)
    skip_mode = await db.get_skip_mode(message.chat.id)
    _language = await db.get_lang(message.chat.id)
    await message.reply_text(
        text=message.lang["start_settings"].format(message.chat.title),
        reply_markup=extra_inline.settings_markup(
            message.lang, admin_only, cmd_delete, pmsg_delete, skip_mode, message.chat.id
        ),
        quote=True,
    )


@app.on_message(filters.new_chat_members, group=7)
@lang.language()
async def _new_member(_, message: types.Message):
    if message.chat.type != enums.ChatType.SUPERGROUP:
        return await message.chat.leave()

    await asyncio.sleep(3)
    for member in message.new_chat_members:
        if member.id == app.id:
            if await db.is_chat(message.chat.id):
                return
            await utils.send_log(message, True)
            await db.add_chat(message.chat.id)
