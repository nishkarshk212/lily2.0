# ALONE-CODER
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import enums

def settings_markup(lang, admin, delete, pmsg_delete, skip, promo, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=lang.get("play_mode", "Admin Only Play") + (" : ON" if admin else " : OFF"),
                callback_data=f"settings play {chat_id}",
                style=enums.ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="Promotional Message : ENABLE" if promo else "Promotional Message : DISABLE",
                callback_data=f"settings promo {chat_id}",
                style=enums.ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("cmd_delete", "Command Delete") + (" : ON" if delete else " : OFF"),
                callback_data=f"settings delete {chat_id}",
                style=enums.ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text="P-Msg Delete: ON" if pmsg_delete else "P-Msg Delete: OFF",
                callback_data=f"settings pmsg_delete {chat_id}",
                style=enums.ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("skip_mode", "Skip Permission") + (" : ON" if skip else " : OFF"),
                callback_data=f"settings skip {chat_id}",
                style=enums.ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("close", "⌯ Close ⌯"),
                callback_data="help close",
                style=enums.ButtonStyle.DANGER,
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
