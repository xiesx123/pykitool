import base64
import hashlib
import json
from typing import Any, Optional

from loguru import logger


# 加密数据
def encrypt(data: Any, password: str = "0123456789") -> Optional[str]:
    try:
        raw = json.dumps(data).encode("utf-8")
        key = hashlib.sha256(password.encode()).digest()
        encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(raw)])
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        return None


# 解密数据
def decrypt(enc_data: str, password: str = "0123456789") -> Any:
    try:
        encrypted = base64.b64decode(enc_data)
        key = hashlib.sha256(password.encode()).digest()
        decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted)])
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        return None


# ================================ 调用示例 ================================

if __name__ == "__main__":

    data = "123456"

    encrypted = encrypt(data)

    print(encrypted)
    print(decrypt(encrypted))
