"""admin 用户初始化 / Admin user initialization on startup."""
from nanoid import generate as nanoid_generate

from linglong_web import LinglongConfig
from linglong_web.utils import logger

from cancan_microstack.services.opsbffsrv.infrastructure.auth.password_service import (
    client_password_hash,
    hash_password,
)
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.admin_user_operate import (
    create_admin_user,
    get_admin_user,
)


async def ensure_admin_user() -> None:
    """启动时检查并创建 admin 用户 / Ensure admin user exists on startup."""
    existing = await get_admin_user("admin")
    if existing is not None:
        logger.info("Admin user already exists, skip creation")
        return

    plain_password = nanoid_generate(size=10)
    # 入库与前端登录口径一致：存 bcrypt(sha256(salt + 明文))，而非 bcrypt(明文)。
    # 用户照常拿到下面打印的“明文”，浏览器登录时会自行 sha256(salt + 明文) 再发。
    # Match the frontend login scheme: store bcrypt(sha256(salt + raw)), not bcrypt(raw). The operator
    # still uses the raw password printed below; the browser hashes it with the same salt at login.
    salt = str(LinglongConfig.get("AUTH_PASSWORD_HASH_SALT", ""))
    hashed = hash_password(client_password_hash(plain_password, salt))
    await create_admin_user("admin", hashed)

    # 安全：初始密码绝不写入文件 logger（server_log_data 是宿主挂载，会落盘泄露）。
    # 仅一次性打印到 stdout，由运维即时读取后保存到安全位置。
    # Security: never write the initial password to the file logger
    # (server_log_data is host-mounted and would persist the secret on disk).
    # Print once to stdout only, for the operator to capture immediately.
    print("=" * 60, flush=True)
    print("ADMIN USER CREATED", flush=True)
    print("Username: admin", flush=True)
    print(f"Password: {plain_password}", flush=True)
    print("Please change the password after first login.", flush=True)
    print("This password is shown ONCE and is NOT written to any log file.", flush=True)
    print("=" * 60, flush=True)
    # 仅在文件日志记录"已创建"事实，不含密码。
    # Record only the creation fact in the file log, without the secret.
    logger.info("Admin user created; initial password printed to stdout once (not logged).")
