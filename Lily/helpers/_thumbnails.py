# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic
#LILY CODER

import os
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from Lily import config
from Lily.helpers import Track


class Thumbnail:
    def __init__(self):
        self.rect = (914, 514)
        self.fill = (255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        self.font1 = ImageFont.truetype("Lily/helpers/Raleway-Bold.ttf", 30)
        self.font2 = ImageFont.truetype("Lily/helpers/Inter-Light.ttf", 30)

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
            return output_path

    async def generate(self, song: Track | Media, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            if not song.thumbnail:
                song.thumbnail = f"https://i.ytimg.com/vi/{song.id}/hqdefault.jpg"
                
            await self.save_thumb(temp, song.thumbnail)
            thumb = Image.open(temp).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            blur = thumb.filter(ImageFilter.GaussianBlur(25))
            image = ImageEnhance.Brightness(blur).enhance(.40)

            _rect = ImageOps.fit(thumb, self.rect, method=Image.LANCZOS, centering=(0.5, 0.5))
            ImageDraw.Draw(self.mask).rounded_rectangle((0, 0, self.rect[0], self.rect[1]), radius=15, fill=255)
            _rect.putalpha(self.mask)
            image.paste(_rect, (183, 30), _rect)

            draw = ImageDraw.Draw(image)
            channel_name = song.channel_name or "YouTube"
            view_count = song.view_count or ""
            draw.text((50, 560), f"{channel_name[:25]} | {view_count}", font=self.font2, fill=self.fill)
            draw.text((50, 600), song.title[:50], font=self.font1, fill=self.fill)
            draw.text((40, 650), "0:01", font=self.font1)
            draw.line([(140, 670), (1160, 670)], fill=self.fill, width=5, joint="curve")
            draw.text((1185, 650), song.duration, font=self.font1, fill=self.fill)

            image.save(output)
            os.remove(temp)
            return output
        except:
            return config.DEFAULT_THUMB
