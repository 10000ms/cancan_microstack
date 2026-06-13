"""bcrypt 密码哈希与验证 / Password hashing and verification with bcrypt."""
import bcrypt


def hash_password(plain: str) -> str:
    """生成 bcrypt 密码哈希 / Generate bcrypt hash for a plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希 / Verify plaintext password against bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
