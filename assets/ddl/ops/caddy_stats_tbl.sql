BEGIN;

CREATE TABLE caddy_stats_tbl
(
    id BIGSERIAL PRIMARY KEY,
    
    -- 时间维度
    stat_time TIMESTAMP WITH TIME ZONE NOT NULL,
    stat_period VARCHAR(20) NOT NULL,
    
    -- 维度信息
    dimension_type VARCHAR(50) NOT NULL,
    dimension_value VARCHAR(255),
    
    -- 请求统计
    total_requests BIGINT DEFAULT 0,
    success_requests BIGINT DEFAULT 0,
    client_error_requests BIGINT DEFAULT 0,
    server_error_requests BIGINT DEFAULT 0,
    
    -- 流量统计
    total_bytes_sent BIGINT DEFAULT 0,
    total_bytes_received BIGINT DEFAULT 0,
    
    -- 性能统计
    avg_response_time INTEGER,
    min_response_time INTEGER,
    max_response_time INTEGER,
    p50_response_time INTEGER,
    p95_response_time INTEGER,
    p99_response_time INTEGER,
    
    -- WAF 统计
    waf_blocked_requests BIGINT DEFAULT 0,
    waf_logged_requests BIGINT DEFAULT 0,
    
    -- 限流统计
    rate_limited_requests BIGINT DEFAULT 0,
    
    -- TLS 统计
    tls_requests BIGINT DEFAULT 0,
    non_tls_requests BIGINT DEFAULT 0,
    
    -- 唯一访客统计
    unique_ips INTEGER DEFAULT 0,
    unique_user_agents INTEGER DEFAULT 0,
    
    -- 元数据
    stats_metadata JSONB DEFAULT '{}',
    
    -- 标准字段
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引（防止重复统计）
CREATE UNIQUE INDEX uk_caddy_stats_tbl_unique ON caddy_stats_tbl (
    stat_time, stat_period, dimension_type, COALESCE(dimension_value, '')
);

-- 提升按更新时间查询效率
CREATE INDEX idx_caddy_stats_tbl_update_time ON caddy_stats_tbl (update_time);

-- 其他业务索引
CREATE INDEX idx_caddy_stats_tbl_time ON caddy_stats_tbl (stat_time DESC);
CREATE INDEX idx_caddy_stats_tbl_period ON caddy_stats_tbl (stat_period);
CREATE INDEX idx_caddy_stats_tbl_dimension ON caddy_stats_tbl (dimension_type, dimension_value);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_caddy_stats_tbl
    BEFORE UPDATE
    ON caddy_stats_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
