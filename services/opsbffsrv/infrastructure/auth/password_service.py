"""bcrypt 密码哈希与验证 / Password hashing and verification with bcrypt."""
import hashlib

import bcrypt


def hash_password(plain: str) -> str:
    """生成 bcrypt 密码哈希 / Generate bcrypt hash for a plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希 / Verify plaintext password against bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def client_password_hash(plain: str, salt: str) -> str:
    """前端预哈希的服务端等价实现 / Server-side equivalent of the client-side pre-hash.

    登录时浏览器发送的不是明文，而是 ``sha256(salt + 明文)`` 的十六进制串；这样真实明文
    永不离开浏览器、永不进入服务端日志，且不同部署用不同 salt → 一处泄露/抓到的 hash 无法
    重放到另一部署。``salt`` 来自服务配置项 ``AUTH_PASSWORD_HASH_SALT``，前后端共用同一值。

    任何"从明文出发"的服务端流程（如引导初始化 admin）必须用本函数算出同一个 hash 再交给
    ``hash_password`` 做 bcrypt，确保入库的 bcrypt 包裹的正是前端日后会提交的那个值。

    The browser never submits the raw password; it submits ``sha256(salt + raw)`` (hex). The real
    plaintext therefore never leaves the browser nor reaches server logs, and a per-deployment salt
    means a hash captured/leaked from one deployment cannot be replayed against another. The salt is
    the ``AUTH_PASSWORD_HASH_SALT`` service config value, shared verbatim by frontend and backend.

    Any server-side flow that starts from a raw password (e.g. admin bootstrap) MUST run it through
    this function before ``hash_password`` so the stored bcrypt wraps the exact value the frontend
    will later submit.

    注意 / Note: 这是 HTTPS 之上的纵深防御，不替代 TLS——它防的是"服务端/日志看到真实明文"，
    传输链路本身仍依赖生产 HTTPS。This is defense-in-depth on top of HTTPS, not a TLS replacement.
    """
    return hashlib.sha256(f"{salt}{plain}".encode("utf-8")).hexdigest()
