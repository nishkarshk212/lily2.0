# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
#LILY CODER

import asyncio
import random
from pyrogram import enums, filters, types

from Lily import app, config, db, lang, logger
from Lily.helpers import buttons, utils, extra_inline


# ── Loading animation frames ──────────────────────────────────────────────────

_LOADING_STEPS = [
    ("⚡", "𝑳𝒐𝒂𝒅𝒊𝒏𝒈 𝑴𝒐𝒅𝒖𝒍𝒆𝒔...",         "▰▱▱▱▱", "20%"),
    ("🎧", "𝑪𝒐𝒏𝒏𝒆𝒄𝒕𝒊𝒏𝒈 𝑽𝒐𝒊𝒄𝒆 𝑪𝒉𝒂𝒕...",  "▰▰▱▱▱", "40%"),
    ("🔍", "𝑺𝒆𝒂𝒓𝒄𝒉𝒊𝒏𝒈 𝑴𝒖𝒔𝒊𝒄 𝑺𝒐𝒖𝒓𝒄𝒆𝒔...", "▰▰▰▱▱", "60%"),
    ("🎶", "𝑶𝒑𝒕𝒊𝒎𝒊𝒛𝒊𝒏𝒈 𝑨𝒖𝒅𝒊𝒐...",       "▰▰▰▰▱", "80%"),
    ("✨", "𝑨𝒍𝒎𝒐𝒔𝒕 𝑹𝒆𝒂𝒅𝒚...",            "▰▰▰▰▰", "100%"),
]

_DONE_TEXT = "🚀 <b>𝑴𝒖𝒔𝒊𝒄 𝑩𝒐𝒕 𝒊𝒔 𝑶𝒏𝒍𝒊𝒏𝒆!</b>"

# Reactions to put on the user's /start command (picks one randomly)
_START_REACTIONS = ["🎵", "🎶", "🎸", "🎹", "🎺", "🎻", "🥁", "🎙"]


def _build_frame(emoji: str, label: str, bar: str, pct: str) -> str:
    return f"{emoji} <b>{label}</b>\n{bar} <code>{pct}</code>"


async def _run_loading_animation(msg: types.Message) -> None:
    """Edit the message through all loading frames with a short delay between each."""
    text = _build_frame(*_LOADING_STEPS[0])
    await msg.edit_text(text)

    for step in _LOADING_STEPS[1:]:
        await asyncio.sleep(0.9)
        # Build cumulative display: show all steps up to current
        idx = _LOADING_STEPS.index(step)
        lines = []
        for prev in _LOADING_STEPS[:idx]:
            lines.append(f"<s>{prev[0]} {prev[1]}</s>  ✅")
        lines.append(_build_frame(*step))
        await msg.edit_text("\n".join(lines))

    # Final "Online!" frame
    await asyncio.sleep(0.8)
    final_lines = []
    for s in _LOADING_STEPS:
        final_lines.append(f"<s>{s[0]} {s[1]}</s>  ✅")
    final_lines.append("")
    final_lines.append(_DONE_TEXT)
    await msg.edit_text("\n".join(final_lines))
    await asyncio.sleep(0.6)


# ─────────────────────────────────────────────────────────────────────────────


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

    # ── React to the user's /start message ───────────────────────────────────
    try:
        reaction = random.choice(_START_REACTIONS)
        await message.react(reaction)
    except Exception:
        pass  # Reactions may not be supported in all chats/versions

    # ── Show animated loading sequence ────────────────────────────────────────
    try:
        loading_msg = await message.reply_text(
            _build_frame(*_LOADING_STEPS[0]),
            quote=not private,
        )
        await _run_loading_animation(loading_msg)
    except Exception as e:
        logger.warning(f"Loading animation error: {e}")
        loading_msg = None

    # ── Send the actual welcome photo/message ─────────────────────────────────
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

    # Delete the loading animation message before sending the welcome card
    if loading_msg:
        try:
            await loading_msg.delete()
        except Exception:
            pass

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
