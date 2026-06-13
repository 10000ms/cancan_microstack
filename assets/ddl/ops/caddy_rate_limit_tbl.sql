BEGIN;

CREATE TABLE caddy_rate_limit_tbl
(
    id BIGSERIAL PRIMARY KEY,
    
    -- 限流规则基本信息
    rule_name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- 匹配条件
    match_type VARCHAR(50) NOT NULL,
    match_pattern VARCHAR(500),
    match_domain VARCHAR(255),
    
    -- 限流配置
    limit_type VARCHAR(50) NOT NULL DEFAULT 'request',
    limit_value INTEGER NOT NULL,
    limit_window INTEGER NOT NULL DEFAULT 60,
    limit_key VARCHAR(50) DEFAULT 'ip',
    
    -- 突发流量配置
    burst_size INTEGER DEFAULT 0,
    
    -- 响应配置
    block_status_code INTEGER DEFAULT 429,
    block_message VARCHAR(500) DEFAULT 'Too Many Requests',
    
    -- 白名单/黑名单
    whitelist_ips TEXT[],
    blacklist_ips TEXT[],
    
    -- 状态和优先级
    is_enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,
    
    -- 元数据
    rule_metadata JSONB DEFAULT '{}',
    
    -- 标准字段
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_caddy_rate_limit_tbl_rule_name ON caddy_rate_limit_tbl (rule_name);

-- 提升按更新时间查询效率
CREATE INDEX idx_caddy_rate_limit_tbl_update_time ON caddy_rate_limit_tbl (update_time);

-- 其他业务索引
CREATE INDEX idx_caddy_rate_limit_tbl_match_type ON caddy_rate_limit_tbl (match_type);
CREATE INDEX idx_caddy_rate_limit_tbl_enabled ON caddy_rate_limit_tbl (is_enabled);
CREATE INDEX idx_caddy_rate_limit_tbl_priority ON caddy_rate_limit_tbl (priority);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_caddy_rate_limit_tbl
    BEFORE UPDATE
    ON caddy_rate_limit_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
