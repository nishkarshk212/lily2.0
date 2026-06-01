import base64
import os

def xor_cipher(data, key):
    return bytearray([b ^ key[i % len(key)] for i, b in enumerate(data)])

files_to_fix = [
    "Lily/helpers/_inline.py",
    "Lily/core/youtube.py"
]

for file_path in files_to_fix:
    if not os.path.exists(file_path):
        continue
    print(f"Fixing {file_path}...")
    with open(file_path, "r") as f:
        content = f.read()
        if '_encoded_payload = "' not in content:
            continue
        payload = content.split('_encoded_payload = "')[1].split('"')[0]
        key = b"ALONE-CODER"
        try:
            decoded = xor_cipher(base64.b64decode(payload), key).decode("utf-8")
            # Replace AloneX with Lily in the decoded content
            fixed = decoded.replace("AloneX", "Lily")
            # Re-encode
            encoded = base64.b64encode(xor_cipher(fixed.encode("utf-8"), key)).decode("utf-8")
            # Update the file content
            new_content = content.replace(payload, encoded)
            with open(file_path, "w") as f:
                f.write(new_content)
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
