# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
# ALONE-CODER

import asyncio
import time
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
        import os
        from Lily import db, queue
        # Cancel color cycle task if running
        if chat_id in self.active_color_tasks:
            task = self.active_color_tasks[chat_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
        # Clean up files for all media items in queue
        q_items = queue.get_queue(chat_id)
        for item in q_items:
            if getattr(item, "file_path", None):
                try:
                    if os.path.exists(item.file_path):
                        os.remove(item.file_path)
                        logger.info(f"[cleanup] Deleted queued file on stop: {item.file_path}")
                except Exception as e:
                    logger.warning(f"[cleanup] Failed to delete {item.file_path} on stop: {e}")

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
        from Lily import app, config, db, lang, logger, yt, xbit, nexgen, aruyt, yt_api
        client = await db.get_assistant(chat_id)
        _play_start = time.time()
        logger.info(f"[play_media] Starting play_media for chat {chat_id}, media: {media.title} ({media.id})")
        
        # MARK CHAT AS ACTIVE RIGHT AWAY TO PREVENT EARLY LEAVE!
        if not seek_time:
            asyncio.create_task(db.add_call(chat_id))
            
        _lang = await lang.get_lang(chat_id)
        _thumb = await thumb.generate(media)

        # All playback uses a local file. Live YouTube stream URLs are NOT used
        # because they are IP/region-locked (NoAudioSourceFound / 403 failures).
        if not media.file_path:
            logger.error(f"[play_media] media.file_path is empty!")
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            return await self.play_next(chat_id)
        logger.info(f"[play_media] Using file_path: {media.file_path}")

        # Optimized FFmpeg args for fast streaming startup
        ffmpeg_args = "-analyzeduration 500000 -probesize 500000 -fflags +nobuffer -flags low_delay"
        if seek_time > 1:
            ffmpeg_args += f" -ss {seek_time}"
        logger.info(f"[play_media] Using FFmpeg args: {ffmpeg_args}")

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.STUDIO,
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
            _call_start = time.time()
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=True),
            )
            _call_elapsed = time.time() - _call_start
            logger.info(f"[play_media] client.play() returned successfully! (took {_call_elapsed:.3f}s)")
            _total_elapsed = time.time() - _play_start
            logger.info(f"[play_media] ✅ Song '{media.title}' is now live in chat {chat_id} — total startup time: {_total_elapsed:.3f}s")

            if not seek_time:
                # Fire-and-forget DB bookkeeping so it never delays the now-playing UI.
                asyncio.create_task(db.increment_played_song(chat_id, video=media.video))

                media.time = 1
                _title_display = media.title[:80] + "…" if len(media.title) > 80 else media.title
                from Lily.helpers import utils
                formatted_duration = utils.format_duration(media.duration_sec)
                text = _lang["play_media"].format(
                    media.url,
                    _title_display,
                    formatted_duration,
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
                    # Use the priority chain (yt.download) first — it leads with
                    # local yt-dlp + COOKIES_DATA, the most reliable path that
                    # bypasses YouTube's bot-block on hosted APIs.
                    local_path = await yt.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and getattr(config, "YT_API_BASE_URL", None):
                        local_path = await yt_api.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and config.XBIT_API_TOKEN:
                        local_path = await xbit.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and getattr(config, "ARUYT_API_KEY", None):
                        local_path = await aruyt.download(media.id, video=media.video)
                    if (not local_path or local_path.startswith(("http://", "https://"))) and config.NEXGENBOTS_API_TOKEN:
                        local_path = await nexgen.download(media.id, video=media.video)
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


    async def _cleanup_file(self, file_path: str) -> None:
        """Delete a local downloaded file to free disk space."""
        import os
        try:
            if file_path and not file_path.startswith(("http://", "https://")):
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"[cleanup] Deleted played file: {file_path}")
        except Exception as e:
            logger.warning(f"[cleanup] Failed to delete {file_path}: {e}")

    async def _disk_guard(self) -> None:
        """Delete all files in downloads/ if disk usage exceeds 80%."""
        import shutil, glob, os
        try:
            total, used, free = shutil.disk_usage("/")
            usage_pct = used / total * 100
            if usage_pct > 80:
                logger.warning(f"[disk_guard] Disk usage {usage_pct:.1f}% — clearing downloads/")
                for f in glob.glob("downloads/*"):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                logger.info("[disk_guard] downloads/ cleared.")
        except Exception as e:
            logger.warning(f"[disk_guard] Error: {e}")

    async def play_next(self, chat_id: int) -> None:
        from Lily import app, config, db, lang, queue, yt, xbit, nexgen, aruyt
        from pyrogram import enums
        import asyncio
        last_media = queue.get_current(chat_id)
        media = queue.get_next(chat_id)

        # Clean up the finished song's file and guard disk space
        if last_media and getattr(last_media, 'file_path', None):
            asyncio.create_task(self._cleanup_file(last_media.file_path))
        asyncio.create_task(self._disk_guard())
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
            logger.info(f"[play_next] Queue is empty for chat {chat_id}")
            await self.stop(chat_id)
            return

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])
        if not media.file_path:
            # Always download a local file for playback. Live YouTube stream URLs
            # are IP/region-locked and cause NoAudioSourceFound / 403, so we never
            # stream live — we play from the downloaded file instead.
            from pathlib import Path
            exts = ["mp4"] if media.video else ["mp3", "webm"]
            for ext in exts:
                fname = f"downloads/{media.id}.{ext}"
                if Path(fname).exists() and Path(fname).stat().st_size > 0:
                    media.file_path = fname
                    break
            if not media.file_path:
                logger.info(f"[play_next] Downloading locally for {media.id}...")
                media.file_path = await yt.download(media.id, video=media.video)

            # If we still have nothing usable, bail out cleanly
            if not media.file_path:
                logger.error(f"[play_next] Download failed for {media.id}")
                await self.stop(chat_id)
                return await msg.edit_text(
                    _lang["error_no_file"].format(config.SUPPORT_CHAT)
                )

            # Verify local file (only when not a stream URL)
            if media.file_path and not (media.file_path.startswith("http") or media.file_path.startswith("https")):
                from pathlib import Path as _P
                if not _P(media.file_path).exists() or _P(media.file_path).stat().st_size == 0:
                    await self.stop(chat_id)
                    return await msg.edit_text(
                        _lang["error_no_file"].format(config.SUPPORT_CHAT)
                    )

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)


    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)


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
