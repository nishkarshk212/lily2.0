# ALONE-CODER
import asyncio
import os
import sys
import shutil
from pathlib import Path
from Lily import logger


async def daily_cache_clear():
    """Clear cache and downloads directories every 24 hours."""
    from Lily import db
    interval = 24 * 60 * 60  # 24 hours in seconds
    while True:
        await asyncio.sleep(interval)
        logger.info("Starting daily cache clear...")
        
        for dir_name in ["cache", "downloads"]:
            target_dir = Path(dir_name)
            if target_dir.exists():
                for item in target_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        logger.error(f"Error clearing {dir_name} item {item}: {e}")
        
        # Clear database media cache
        try:
            deleted = await db.clear_media_cache()
            logger.info(f"Cleared {deleted} entries from DB media cache.")
        except Exception as e:
            logger.error(f"Error clearing DB media cache: {e}")
            
        logger.info("Daily cache clear completed.")


async def auto_maintenance():
    """
    Combined maintenance task that runs daily.
    """
    # Start the task
    asyncio.create_task(daily_cache_clear())
    
    # Keep the maintenance task alive
    while True:
        await asyncio.sleep(3600)  # Check hourly (just to keep task alive)
