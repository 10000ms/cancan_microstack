BEGIN;

CREATE TABLE caddy_certificate_tbl
(
    id BIGSERIAL PRIMARY KEY,
    
    -- 域名信息
    domain VARCHAR(255) NOT NULL,
    alt_domains TEXT[],
    
    -- 证书信息
    certificate_pem TEXT,
    private_key_pem TEXT,
    issuer VARCHAR(255),
    
    -- 证书时间
    issued_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    auto_renew BOOLEAN DEFAULT true,
    renew_before_days INTEGER DEFAULT 30,
    
    -- 证书状态
    status VARCHAR(50) DEFAULT 'pending',
    last_renew_attempt TIMESTAMP WITH TIME ZONE,
    last_renew_success TIMESTAMP WITH TIME ZONE,
    renew_error TEXT,
    
    -- ACME 配置
    acme_provider VARCHAR(100) DEFAULT 'letsencrypt',
    acme_email VARCHAR(255),
    acme_challenge_type VARCHAR(50) DEFAULT 'http-01',
    
    -- 元数据
    certificate_metadata JSONB DEFAULT '{}',
    
    -- 标准字段
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_caddy_certificate_tbl_domain ON caddy_certificate_tbl (domain);

-- 提升按更新时间查询效率
CREATE INDEX idx_caddy_certificate_tbl_update_time ON caddy_certificate_tbl (update_time);

-- 其他业务索引
CREATE INDEX idx_caddy_certificate_tbl_status ON caddy_certificate_tbl (status);
CREATE INDEX idx_caddy_certificate_tbl_expires_at ON caddy_certificate_tbl (expires_at);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_caddy_certificate_tbl
    BEFORE UPDATE
    ON caddy_certificate_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
