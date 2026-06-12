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


def is_pid_running(pid):
    """Check if a PID is actually running"""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
    except OSError as err:
        if err.errno == errno.ESRCH:
            # ESRCH = No such process
            return False
        elif err.errno == errno.EPERM:
            # EPERM = Permission denied, but process exists
            return True
        else:
            raise
    else:
        return True


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
    # PID lock implementation
    lock_file = None
    try:
        # First check if PID file exists and process is running
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r") as f:
                    old_pid = int(f.read().strip())
                if is_pid_running(old_pid):
                    print(f"ERROR: Another instance of Lily is already running (PID {old_pid})!")
                    print(f"PID file: {PID_FILE}")
                    sys.exit(1)
                else:
                    # Stale PID file - remove it
                    os.remove(PID_FILE)
                    print(f"Removed stale PID file for PID {old_pid}")
            except (ValueError, IOError):
                # Invalid PID or error reading file - remove it
                try:
                    os.remove(PID_FILE)
                except:
                    pass

        # Open lock file and acquire lock
        lock_file = open(PID_FILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write our PID
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        try:
            asyncio.get_event_loop().run_until_complete(main())
        except KeyboardInterrupt:
            pass
    finally:
        # Clean up
        if lock_file:
            try:
                lock_file.close()
            except:
                pass
            try:
                os.remove(PID_FILE)
            except:
                pass
