# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
# ALONE-CODER

import asyncio
from Lily import logger
# pyrefly: ignore [missing-import]
from ntgcalls import (ConnectionNotFound, TelegramServerError,
                      RTMPStreamingUnsupported)
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from Lily.helpers import Media, Track, buttons, thumb


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []
        self.active_color_tasks = {}  # chat_id: task_obj
        
    async def cycle_button_colors(self, chat_id: int, message_id: int):
        from pyrogram import enums
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from Lily import app, db, queue
        
        # Define style cycles
        control_styles_cycle = [
            [enums.ButtonStyle.PRIMARY, enums.ButtonStyle.SUCCESS, enums.ButtonStyle.DANGER, enums.ButtonStyle.PRIMARY, enums.ButtonStyle.SUCCESS],
            [enums.ButtonStyle.SUCCESS, enums.ButtonStyle.DANGER, enums.ButtonStyle.PRIMARY, enums.ButtonStyle.SUCCESS, enums.ButtonStyle.DANGER],
            [enums.ButtonStyle.DANGER, enums.ButtonStyle.PRIMARY, enums.ButtonStyle.SUCCESS, enums.ButtonStyle.DANGER, enums.ButtonStyle.PRIMARY],
        ]
        slide_bar_styles_cycle = [
            enums.ButtonStyle.PRIMARY,
            enums.ButtonStyle.SUCCESS,
            enums.ButtonStyle.DANGER,
        ]
        cycle_index = 0
        
        try:
            while True:
                # Check if call is still active
                if not await db.get_call(chat_id):
                    break
                
                # Get current media to ensure message is still valid
                media = queue.get_current(chat_id)
                if not media or media.message_id != message_id:
                    break
                
                # Get current message
                msg = await app.get_messages(chat_id, message_id)
                if not msg or not msg.reply_markup:
                    break
                
                new_rows = []
                # Handle slide bar (status/timer) row
                if msg.reply_markup.inline_keyboard:
                    first_row = msg.reply_markup.inline_keyboard[0]
                    if len(first_row) == 1 and first_row[0].callback_data and first_row[0].callback_data.startswith("controls status"):
                        # Update slide bar button color
                        slide_bar_style = slide_bar_styles_cycle[cycle_index % len(slide_bar_styles_cycle)]
                        slide_bar_btn = InlineKeyboardButton(
                            text=first_row[0].text,
                            callback_data=first_row[0].callback_data,
                            style=slide_bar_style
                        )
                        new_rows.append([slide_bar_btn])
                
                # Get current control styles
                current_control_styles = control_styles_cycle[cycle_index % len(control_styles_cycle)]
                
                # Add control buttons row with new styles
                new_rows.append([
                    InlineKeyboardButton(text="▷", callback_data=f"controls resume {chat_id}", style=current_control_styles[0]),
                    InlineKeyboardButton(text="II", callback_data=f"controls pause {chat_id}", style=current_control_styles[1]),
                    InlineKeyboardButton(text="⥁", callback_data=f"controls replay {chat_id}", style=current_control_styles[2]),
                    InlineKeyboardButton(text="‣‣I", callback_data=f"controls skip {chat_id}", style=current_control_styles[3]),
                    InlineKeyboardButton(text="▢", callback_data=f"controls stop {chat_id}", style=current_control_styles[4]),
                ])
                
                # Build new keyboard
                new_keyboard = InlineKeyboardMarkup(new_rows)
                
                # Update the message
                try:
                    await app.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=new_keyboard
                    )
                except Exception as e:
                    from Lily import logger
                    logger.warning(f"Failed to update button colors: {e}")
                    break
                
                cycle_index += 1
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            if chat_id in self.active_color_tasks:
                del self.active_color_tasks[chat_id]

    async def pause(self, chat_id: int) -> bool:
        from Lily import db
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        from Lily import db
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        from Lily import db, queue
        # Cancel color cycle task if running
        if chat_id in self.active_color_tasks:
            task = self.active_color_tasks[chat_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
        client = await db.get_assistant(chat_id)
        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except:
            pass

        try:
            await client.leave_call(chat_id, close=False)
        except:
            pass


    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        from Lily import app, config, db, lang, logger, yt, xbit, nexgen, aruyt
        from Lily.plugins.play import send_related_songs
        client = await db.get_assistant(chat_id)
        logger.info(f"[play_media] Starting play_media for chat {chat_id}, media: {media.title} ({media.id})")
        
        # MARK CHAT AS ACTIVE RIGHT AWAY TO PREVENT EARLY LEAVE!
        if not seek_time:
            await db.add_call(chat_id)
            
        _lang = await lang.get_lang(chat_id)
        _thumb = await thumb.generate(media)

        if not media.file_path:
            logger.error(f"[play_media] media.file_path is empty!")
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            return await self.play_next(chat_id)
        logger.info(f"[play_media] Using file_path: {media.file_path}")

        # Simplified FFmpeg args to avoid issues
        ffmpeg_args = "-analyzeduration 20M -probesize 20M"
        if seek_time > 1:
            ffmpeg_args += f" -ss {seek_time}"
        logger.info(f"[play_media] Using FFmpeg args: {ffmpeg_args}")

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg_args,
        )
        try:
            logger.info(f"[play_media] Calling client.play() for chat {chat_id}")
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=True),
            )
            logger.info(f"[play_media] client.play() returned successfully!")
            if not seek_time:
                media.time = 1
                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)
                try:
                    await message.edit_media(
                        media=InputMediaPhoto(
                            media=_thumb,
                            caption=text,
                            has_spoiler=True,
                        ),
                        reply_markup=keyboard,
                    )
                except MessageIdInvalid:
                    media.message_id = (await app.send_photo(
                        chat_id=chat_id,
                        photo=_thumb,
                        caption=text,
                        reply_markup=keyboard,
                        has_spoiler=True,
                    )).id
                
                # Send related songs after a short delay
                async def send_suggestions():
                    try:
                        await asyncio.sleep(2)
                        if media.user_id:
                            await send_related_songs(chat_id, media.user_id, media, message)
                    except Exception as e:
                        logger.error(f"[send_suggestions] Error: {e}")
                asyncio.create_task(send_suggestions())
                
                # Start button color cycle task
                if chat_id in self.active_color_tasks:
                    old_task = self.active_color_tasks[chat_id]
                    old_task.cancel()
                    try:
                        await old_task
                    except asyncio.CancelledError:
                        pass
                color_task = asyncio.create_task(self.cycle_button_colors(chat_id, media.message_id))
                self.active_color_tasks[chat_id] = color_task
        except FileNotFoundError as e:
            logger.error(f"[play_media] FileNotFoundError: {e}, file: {media.file_path}")
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall as e:
            logger.error(f"[play_media] NoActiveGroupCall: {e}")
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound as e:
            logger.error(f"[play_media] NoAudioSourceFound: {e} for {media.title} ({media.id}) at {media.file_path}")
            if media.file_path.startswith(("http://", "https://")):
                logger.info(f"[play_media] Attempting fallback download for {media.id}...")
                try:
                    await message.edit_text(_lang["play_downloading"])
                except Exception:
                    pass

                try:
                    # Use priority order (aruyt → xbit → nexgen → yt_api → yt) for fallback
                    from Lily import yt_api
                    local_path = None
                    if config.ARUYT_API_KEY:
                        local_path = await aruyt.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and config.XBIT_API_TOKEN:
                        local_path = await xbit.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and config.NEXGENBOTS_API_TOKEN:
                        local_path = await nexgen.download(media.id, video=media.video)
                    if not local_path or local_path.startswith(("http://", "https://")):
                        local_path = await yt_api.download(media.id, video=media.video)
                    if not local_path or local_path.startswith(("http://", "https://")):
                        local_path = await yt.download(media.id, video=media.video)
                    if local_path and not local_path.startswith(("http://", "https://")):
                        logger.info(f"[play_media] Fallback download successful: {local_path}")
                        media.file_path = local_path
                        return await self.play_media(chat_id, message, media, seek_time)
                except Exception as e:
                    logger.exception(f"[play_media] Fallback download failed for {media.id}: {e}")

            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
        except (ConnectionNotFound, TelegramServerError) as e:
            logger.error(f"[play_media] Telegram server error: {type(e).__name__} - {e}")
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])
        except RTMPStreamingUnsupported as e:
            logger.error(f"[play_media] RTMPStreamingUnsupported: {e}")
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])
        except Exception as e:
            logger.exception(f"[play_media] Unexpected error playing {media.title}: {type(e).__name__} - {e}")
            await self.play_next(chat_id)


    async def replay(self, chat_id: int) -> None:
        from Lily import app, db, lang, queue
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        await self.play_media(chat_id, msg, media)


    async def play_next(self, chat_id: int) -> None:
        from Lily import app, config, db, lang, queue, yt, xbit, nexgen, aruyt
        last_media = queue.get_current(chat_id)
        media = queue.get_next(chat_id)
        try:
            if media and media.message_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=media.message_id,
                    revoke=True,
                )
                media.message_id = 0
        except:
            pass

        if not media:
            await self.stop(chat_id)
            if last_media:
                try:
                    from Lily.plugins.play import get_related_songs
                    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    user_id = last_media.user_id or config.OWNER_ID

                    related_songs = await get_related_songs(last_media, limit=6)
                    if related_songs:
                        await db.set_temp_data(f"related_songs:{chat_id}:{user_id}", related_songs)
                        kb_rows = []
                        for i in range(min(3, len(related_songs))):
                            song = related_songs[i]
                            title_short = song["title"][:36] + ("…" if len(song["title"]) > 36 else "")
                            kb_rows.append([
                                InlineKeyboardButton(
                                    text=f"♪ {title_short}",
                                    callback_data=f"add_related {i} {chat_id} {user_id}"
                                )
                            ])
                        # Add navigation buttons - More/Close
                        nav_buttons = []
                        if len(related_songs) > 3:
                            nav_buttons.append(InlineKeyboardButton(
                                text="☛ More",
                                callback_data=f"more_related 1 {chat_id} {user_id}"
                            ))
                        nav_buttons.append(InlineKeyboardButton(
                            text="✕",
                            callback_data=f"dismiss_related {chat_id} {user_id}"
                        ))
                        if nav_buttons:
                            kb_rows.append(nav_buttons)
                        
                        rec_msg = await app.send_message(
                            chat_id=chat_id,
                            text="𝗥𝗲𝗰𝗼𝗺𝗺𝗲𝗻𝗱 𝗼𝗻 𝘆𝗼𝘂𝗿 𝗰𝗵𝗼𝗶𝗰𝗲 :",
                            reply_markup=InlineKeyboardMarkup(kb_rows),
                        )
                        
                        # Auto-delete after 60 seconds
                        import asyncio
                        asyncio.create_task(self._delete_after_delay(chat_id, rec_msg.id, 60))
                except Exception as e:
                    logger.error(f"[play_next] Related songs error: {e}")
            return 

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])
        if not media.file_path:
            # Check cache
            cache = await db.get_media_cache(media.id)
            if cache:
                media.file_path = cache.get("video_url") if media.video else cache.get("audio_url")
            
            if not media.file_path:
                from Lily import yt_api
                if config.ARUYT_API_KEY:
                    media.file_path = await aruyt.download(media.id, video=media.video)
                if not media.file_path and config.XBIT_API_TOKEN:
                    media.file_path = await xbit.download(media.id, video=media.video)
                if not media.file_path and config.NEXGENBOTS_API_TOKEN:
                    media.file_path = await nexgen.download(media.id, video=media.video)
                if not media.file_path:
                    media.file_path = await yt_api.download(media.id, video=media.video)
                if not media.file_path:
                    media.file_path = await yt.download(media.id, video=media.video)
                # Save to cache if it's a URL
                if media.file_path and (media.file_path.startswith("http") or media.file_path.startswith("https")):
                    cache_data = {
                        "title": media.title,
                        "duration": media.duration,
                        "duration_sec": media.duration_sec,
                        ("video_url" if media.video else "audio_url"): media.file_path
                    }
                    await db.save_media_cache(media.id, cache_data)
            
            if not media.file_path:
                await self.stop(chat_id)
                return await msg.edit_text(
                    _lang["error_no_file"].format(config.SUPPORT_CHAT)
                )
            
            # Verify local file
            from pathlib import Path
            if media.file_path and not (media.file_path.startswith("http") or media.file_path.startswith("https")):
                if not Path(media.file_path).exists() or Path(media.file_path).stat().st_size == 0:
                    await self.stop(chat_id)
                    return await msg.edit_text(
                        _lang["error_no_file"].format(config.SUPPORT_CHAT)
                    )

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)


    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)

    async def _delete_after_delay(self, chat_id: int, message_id: int, delay: int) -> None:
        """Delete a message after a specified delay in seconds."""
        import asyncio
        from Lily import app
        await asyncio.sleep(delay)
        try:
            await app.delete_messages(chat_id=chat_id, message_ids=message_id)
        except:
            pass


    async def decorators(self, client: PyTgCalls) -> None:
        from Lily import app, db, logger, queue
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
            logger.info(f"[pytgcalls] Update received: {type(update)}, raw: {update}")
            if isinstance(update, types.StreamEnded):
                logger.info(f"[pytgcalls] Stream ended: {update}")
                if update.stream_type == types.StreamEnded.Type.AUDIO:
                    chat_id = update.chat_id
                    if await db.get_playmsg_delete(chat_id):
                        media = queue.get_current(chat_id)
                        if media and media.message_id:
                            try:
                                await app.delete_messages(chat_id, media.message_id)
                            except Exception as e:
                                logger.warning(f"Failed to delete play message: {e}")
                    await self.play_next(chat_id)
            elif isinstance(update, types.ChatUpdate):
                logger.info(f"[pytgcalls] Chat update: chat_id={update.chat_id}, status={update.status}")
                chat_id = update.chat_id
                # Only stop the call if we actually have a call for this chat AND the status is a real stop
                has_call = await db.get_call(chat_id)
                logger.info(f"[pytgcalls] Chat {chat_id} has active call? {has_call}")
                if has_call and update.status in [
                    types.ChatUpdate.Status.KICKED,
                    types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                ]:
                    logger.info(f"ChatUpdate: stopping call for chat {chat_id} with status {update.status}")
                    await self.stop(update.chat_id)
                else:
                    logger.info(f"ChatUpdate: ignoring status {update.status} for chat {chat_id}")


    async def boot(self) -> None:
        from Lily import logger, userbot
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")
