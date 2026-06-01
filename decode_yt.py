import base64

def xor_cipher(data, key):
    return bytearray([b ^ key[i % len(key)] for i, b in enumerate(data)])

with open("Lily/core/youtube.py", "r") as f:
    content = f.read()
    payload = content.split('_encoded_payload = "')[1].split('"')[0]
    key = b"ALONE-CODER"
    decoded = xor_cipher(base64.b64decode(payload), key).decode("utf-8")
    with open("decoded_youtube.py", "w") as f2:
        f2.write(decoded)
