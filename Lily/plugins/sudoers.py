# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


from pyrogram import filters, types

from Lily import app, db, lang
from Lily.helpers import utils, delete_cmd


@app.on_message(filters.command(["addsudo", "delsudo", "rmsudo"]) & filters.user(app.owner))
@lang.language()
@delete_cmd
async def _sudo(_, m: types.Message):
    user = await utils.extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if m.command[0] == "addsudo":
        if user.id in app.sudoers:
            return await m.reply_text(m.lang["sudo_already"].format(user.mention))

        app.sudoers.add(user.id)
        await db.add_sudo(user.id)
        await m.reply_text(m.lang["sudo_added"].format(user.mention))
    else:
        if user.id not in app.sudoers:
            return await m.reply_text(m.lang["sudo_not"].format(user.mention))

        app.sudoers.discard(user.id)
        await db.del_sudo(user.id)
        await m.reply_text(m.lang["sudo_removed"].format(user.mention))


o_mention = None

@app.on_message(filters.command(["listsudo", "sudolist"]))
@lang.language()
@delete_cmd
async def _listsudo(_, m: types.Message):
    global o_mention
    sent = await m.reply_text(m.lang["sudo_fetching"])

    if not o_mention:
        o_mention = (await app.get_users(app.owner)).mention
    txt = m.lang["sudo_owner"].format(o_mention)
    sudoers = await db.get_sudoers()
    if sudoers:
        txt += m.lang["sudo_users"]

    for user_id in sudoers:
        try:
            user = (await app.get_users(user_id)).mention
            txt += f"\n- {user}"
        except:
            continue

    await sent.edit_text(txt)


@app.on_message(filters.command(["clearcache", "cc"]) & app.sudoers)
@lang.language()
@delete_cmd
async def _clearcache(_, m: types.Message):
    deleted = await db.clear_media_cache()
    await m.reply_text(f"Media cache cleared! Deleted {deleted} entries.")


@app.on_message(filters.command(["update"]) & app.sudoers)
@lang.language()
@delete_cmd
async def _update(_, m: types.Message):
    import os
    import sys
    import asyncio
    from subprocess import Popen, PIPE

    sent = await m.reply_text("Pulling latest changes from git...")
    
    # Pull latest changes
    try:
        process = Popen(["git", "pull"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        output = stdout.decode() + stderr.decode()
        
        if "Already up to date" in output:
            await sent.edit_text("Bot is already up to date!")
            return
            
        await sent.edit_text(f"Changes pulled:\n{output}\n\nRestarting bot...")
    except Exception as e:
        await sent.edit_text(f"Error pulling updates: {str(e)}")
        return
    
    # Restart the bot
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable, "-m", "Lily"])
