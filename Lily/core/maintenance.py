# ALONE-CODER
import asyncio
import os
import sys
import shutil
from pathlib import Path
from Lily import logger


async def daily_cache_clear():
    """Clear cache directory every 24 hours."""
    interval = 24 * 60 * 60  # 24 hours in seconds
    while True:
        await asyncio.sleep(interval)
        logger.info("Starting daily cache clear...")
        
        cache_dir = Path("cache")
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    logger.error(f"Error clearing cache item {item}: {e}")
        
        logger.info("Daily cache clear completed.")


async def weekly_storage_clear():
    """Clear downloads/storage every 7 days."""
    interval = 7 * 24 * 60 * 60  # 7 days in seconds
    while True:
        await asyncio.sleep(interval)
        logger.info("Starting weekly storage clear...")
        
        downloads_dir = Path("downloads")
        if downloads_dir.exists():
            for item in downloads_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    logger.error(f"Error clearing storage item {item}: {e}")
        
        logger.info("Weekly storage clear completed.")


async def auto_maintenance():
    """
    Combined maintenance task that runs both daily cache clear and weekly storage clear.
    """
    # Start both tasks
    asyncio.create_task(daily_cache_clear())
    asyncio.create_task(weekly_storage_clear())
    
    # Keep the maintenance task alive
    while True:
        await asyncio.sleep(3600)  # Check hourly (just to keep task alive)
