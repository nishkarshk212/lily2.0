# ALONE-CODER
import asyncio
import os
import sys
import shutil
from pathlib import Path
from Lily import logger

async def auto_maintenance():
    """
    Periodic task to clear cache and restart the bot every 7 days.
    """
    # 7 days in seconds
    interval = 7 * 24 * 60 * 60
    
    while True:
        await asyncio.sleep(interval)
        
        logger.info("Starting scheduled 7-day maintenance...")
        
        # 1. Clear Local Cache & Downloads
        for directory in ["cache", "downloads"]:
            dir_path = Path(directory)
            if dir_path.exists():
                for item in dir_path.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        logger.error(f"Error clearing {item}: {e}")
        
        logger.info("Local cache and downloads cleared.")
        
        # 2. Restart the bot
        # This will replace the current process with a new one
        logger.info("Scheduled restart initiated...")
        os.execl(sys.executable, sys.executable, "-m", "Lily")
