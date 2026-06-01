# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


from pyrogram import filters, types

from Lily import anon, app, db, lang
from Lily.helpers import can_skip


@app.on_message(filters.command(["skip", "next"]) & filters.group & ~app.bl_users)
@lang.language()
@can_skip
async def _skip(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    await anon.play_next(m.chat.id)
    await m.reply_text(m.lang["play_skipped"].format(m.from_user.mention))
