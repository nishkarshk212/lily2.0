# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic

from pyrogram import filters, types
from Lily import app, db, config
from Lily.helpers import delete_cmd

@app.on_message(filters.command(["usage"]) & filters.group & ~app.bl_users)
@delete_cmd
async def _usage(_, m: types.Message):
    # Fetch usage stats from the database
    stats = await db.get_usage(m.chat.id)
    
    global_stats = stats.get("global") or {"total": 0, "audio": 0, "video": 0}
    chat_stats = stats.get("chat") or {"total": 0, "audio": 0, "video": 0}

    text = (
        "📊 <b><u>𝐋ɪʟʏ 𝐌ᴜsɪᴄ - 𝐔sᴀɢᴇ 𝐒ᴛᴀᴛs</u></b>\n\n"
        "📍 <b>𝐂ʜᴀᴛ 𝐔sᴀɢᴇ (𝐓ʜɪs 𝐆ʀᴏᴜᴘ):</b>\n"
        f"• <b>Total Plays:</b> <code>{chat_stats.get('total', 0)}</code>\n"
        f"• <b>Audio Tracks:</b> <code>{chat_stats.get('audio', 0)}</code>\n"
        f"• <b>Video Streams:</b> <code>{chat_stats.get('video', 0)}</code>\n\n"
        "🌍 <b>𝐆ʟᴏʙᴀʟ 𝐔sᴀɢᴇ (𝐒ʏsᴛᴇᴍ-ᴡɪᴅᴇ):</b>\n"
        f"• <b>Total Plays:</b> <code>{global_stats.get('total', 0)}</code>\n"
        f"• <b>Audio Tracks:</b> <code>{global_stats.get('audio', 0)}</code>\n"
        f"• <b>Video Streams:</b> <code>{global_stats.get('video', 0)}</code>\n\n"
        "⚡ <i>Powered by LilyMusic</i>"
    )

    if config.PING_IMG:
        try:
            await m.reply_photo(
                photo=config.PING_IMG,
                caption=text,
            )
        except Exception:
            await m.reply_text(text)
    else:
        await m.reply_text(text)
