# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of LilyMusic


from dataclasses import dataclass


@dataclass
class Media:
    id: str
    duration: str
    duration_sec: int
    file_path: str
    message_id: int
    title: str
    url: str
    time: int = 0
    user: str = None
    user_id: int = None
    video: bool = False


@dataclass
class Track:
    id: str
    channel_name: str
    duration: str
    duration_sec: int
    title: str
    url: str
    file_path: str = None
    message_id: int = 0
    time: int = 0
    thumbnail: str = None
    user: str = None
    user_id: int = None
    view_count: str = None
    video: bool = False
