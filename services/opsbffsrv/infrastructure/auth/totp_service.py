"""TOTP 封装 / TOTP service wrapping pyotp + Fernet encryption."""
import base64
import io

import pyotp
import qrcode
from cryptography.fernet import Fernet

from linglong_web import LinglongConfig


def _get_fernet() -> Fernet:
    """获取 Fernet 实例 / Get Fernet instance from config."""
    key = LinglongConfig.get("AUTH_TOTP_FERNET_KEY")
    if not key:
        raise RuntimeError("AUTH_TOTP_FERNET_KEY is not configured")
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def generate_secret() -> str:
    """生成 TOTP base32 secret / Generate a random TOTP base32 secret."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    """Fernet 加密 TOTP secret / Encrypt TOTP secret with Fernet."""
    f = _get_fernet()
    return f.encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str) -> str:
    """Fernet 解密 TOTP secret / Decrypt TOTP secret with Fernet."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    """验证 TOTP 码 / Verify a TOTP code against secret (±30s window)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_provisioning_uri(secret: str, username: str) -> str:
    """生成 otpauth URI / Generate provisioning URI for authenticator apps."""
    issuer = LinglongConfig.get("AUTH_TOTP_ISSUER", "OPS Admin")
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def generate_qr_base64(uri: str) -> str:
    """生成 QR 二维码 base64 / Generate QR code as data URI base64 PNG."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
