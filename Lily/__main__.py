# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


import asyncio
import importlib
import os
import sys
import fcntl
import errno
import signal

from pyrogram import idle

from Lily import (anon, app, config, db,
                   logger, stop, userbot, yt)
from Lily.core.maintenance import auto_maintenance
from Lily.plugins import all_modules


# PID lock file path (use absolute path to avoid issues)
# __file__ is in Lily/__main__.py, so project root is one level up
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lily.pid")
PID_FILE = os.path.abspath(PID_FILE)


async def main():
    await db.connect()
    await app.boot()
    await userbot.boot()
    await anon.boot()

    for module in all_modules:
        importlib.import_module(f"Lily.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    asyncio.create_task(auto_maintenance())

    await idle()
    await stop()


if __name__ == "__main__":
    # Single-instance guard.
    #
    # We rely SOLELY on an exclusive flock(2) on the PID file. This is the
    # correct primitive because the kernel releases the lock automatically
    # whenever the holding process dies (even on SIGKILL / OOM), so a stale
    # lock can never survive a crash.
    #
    # A pid-comparison pre-check (read pid from file, os.kill(pid, 0)) is NOT
    # used on purpose: when the bot is launched via `bash start`, bash is PID 1
    # and python is always PID 2. After a SIGKILL the leftover file still
    # contains "2", and every restart re-spawns python as PID 2, so the check
    # would always report "another instance is already running" and deadlock
    # the container in a restart loop. flock has no such failure mode.
    lock_file = None
    try:
        lock_file = open(PID_FILE, 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            if err.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                print(f"ERROR: Another instance of Lily is already running "
                      f"(lock held on {PID_FILE})!")
                sys.exit(1)
            raise

        # Write our PID for informational/debugging purposes only.
        lock_file.write(str(os.getpid()))
        lock_file.flush()

        try:
            asyncio.get_event_loop().run_until_complete(main())
        except KeyboardInterrupt:
            pass
    finally:
        # Clean up. Closing the fd releases the flock; removing the file avoids
        # leaving a dangling file behind on a clean shutdown.
        if lock_file:
            try:
                lock_file.close()
            except OSError:
                pass
            try:
                os.remove(PID_FILE)
            except OSError:
                pass
