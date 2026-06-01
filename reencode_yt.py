import base64

def xor_cipher(data, key):
    return bytearray([b ^ key[i % len(key)] for i, b in enumerate(data)])

with open("decoded_youtube.py", "r") as f:
    fixed = f.read()
    key = b"ALONE-CODER"
    encoded = base64.b64encode(xor_cipher(fixed.encode("utf-8"), key)).decode("utf-8")
    
    new_content = f"""# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License
# This file is part of LilyMusic
# ALONE-CODER

import base64

def xor_cipher(data, key):
    return bytearray([b ^ key[i % len(key)] for i, b in enumerate(data)])

_encoded_payload = "{encoded}"

_key = b"ALONE-CODER"

exec(xor_cipher(base64.b64decode(_encoded_payload), _key).decode("utf-8"), globals())
"""
    
with open("Lily/core/youtube.py", "w") as f:
    f.write(new_content)
