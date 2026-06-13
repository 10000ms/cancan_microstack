BEGIN;

CREATE TABLE admin_user_tbl
(
    id                      BIGSERIAL PRIMARY KEY,
    username                VARCHAR(50) NOT NULL,
    password_hash           VARCHAR(255) NOT NULL,
    totp_secret_encrypted   TEXT,
    totp_bound              BOOLEAN DEFAULT false,
    flag                    SMALLINT DEFAULT 0,
    created_time            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time             TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_admin_user_tbl_username ON admin_user_tbl (username);

-- 提升按更新时间查询效率
CREATE INDEX idx_admin_user_tbl_update_time ON admin_user_tbl (update_time);

-- 自动更新时间戳触发器
CREATE TRIGGER t_admin_user_tbl
    BEFORE UPDATE
    ON admin_user_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMENT ON TABLE admin_user_tbl IS 'OPS Admin 用户表';
COMMENT ON COLUMN admin_user_tbl.username IS '用户名';
COMMENT ON COLUMN admin_user_tbl.password_hash IS 'bcrypt 密码哈希';
COMMENT ON COLUMN admin_user_tbl.totp_secret_encrypted IS 'Fernet 加密后的 TOTP secret';
COMMENT ON COLUMN admin_user_tbl.totp_bound IS 'TOTP 是否已绑定';
COMMENT ON COLUMN admin_user_tbl.flag IS '标记位 0=正常';

COMMIT;
