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
    import shutil
    import asyncio
    from subprocess import Popen, PIPE
    from Lily import stop

    sent = await m.reply_text("Pulling latest changes from git...")
    
    # Root directory of the project
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Pull latest changes
    try:
        process = Popen(["git", "pull"], cwd=root_dir, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        output = stdout.decode() + stderr.decode()
        
        # Check if force flag is present
        force = len(m.command) > 1 and m.command[1].lower() == "force"
        
        if "Already up to date" in output and not force:
            await sent.edit_text("Bot is already up to date! (Use `/update force` to force restart/pull)")
            return
            
        await sent.edit_text(f"Changes pulled:\n<code>{output}</code>\n\nStopping bot and performing cleanup...")
    except Exception as e:
        await sent.edit_text(f"Error pulling updates: {str(e)}")
        return
    
    # Clean up temp directories to prevent stale download files
    for directory in ["cache", "downloads"]:
        shutil.rmtree(directory, ignore_errors=True)
        
    try:
        os.remove("log.txt")
    except:
        pass

    # Stop client sessions and task runner safely
    asyncio.create_task(stop())
    await asyncio.sleep(2)
    
    # Exec replacement process
    os.execl(sys.executable, sys.executable, "-m", "Lily")


@app.on_message(filters.command(["groupdetail", "groups"]) & filters.user(app.owner))
@lang.language()
@delete_cmd
async def _groupdetail(_, m: types.Message):
    """Show group details - bot owner only."""
    sent = await m.reply_text("Fetching group details...")
    
    try:
        dialogs = []
        async for dialog in app.get_dialogs():
            if dialog.chat.type in ["group", "supergroup"]:
                try:
                    chat = await app.get_chat(dialog.chat.id)
                    member_count = chat.members_count if hasattr(chat, 'members_count') else "Unknown"
                    dialogs.append({
                        'id': dialog.chat.id,
                        'title': chat.title,
                        'username': f"@{chat.username}" if chat.username else "Private",
                        'member_count': member_count,
                        'type': dialog.chat.type
                    })
                except Exception as e:
                    continue
        
        if not dialogs:
            await sent.edit_text("📊 **Group Details**\n\nNo groups found.")
            return
        
        # Sort by member count
        dialogs.sort(key=lambda x: x['member_count'] if isinstance(x['member_count'], int) else 0, reverse=True)
        
        # Build response message
        txt = f"📊 **Group Details**\n\n"
        txt += f"📈 Total Groups: `{len(dialogs)}`\n\n"
        
        for i, group in enumerate(dialogs, 1):
            txt += (
                f"**{i}. {group['title']}**\n"
                f"   🆔 ID: `{group['id']}`\n"
                f"   👥 Members: `{group['member_count']}`\n"
                f"   🔗 {group['username']}\n"
                f"   📁 Type: {group['type']}\n\n"
            )
        
        await sent.edit_text(txt)
        
    except Exception as e:
        await sent.edit_text(f"❌ Error fetching group details: {str(e)}")
