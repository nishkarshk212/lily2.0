# ALONE-CODER
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def settings_markup(lang, admin, delete, pmsg_delete, skip, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=lang.get("play_mode", "Admin Only Play") + (" : ON" if admin else " : OFF"),
                callback_data=f"settings play {chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("cmd_delete", "Command Delete") + (" : ON" if delete else " : OFF"),
                callback_data=f"settings delete {chat_id}",
            ),
            InlineKeyboardButton(
                text="P-Msg Delete: ON" if pmsg_delete else "P-Msg Delete: OFF",
                callback_data=f"settings pmsg_delete {chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("skip_mode", "Skip Permission") + (" : ON" if skip else " : OFF"),
                callback_data=f"settings skip {chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=lang.get("close", "⌯ Close ⌯"),
                callback_data="help close",
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
