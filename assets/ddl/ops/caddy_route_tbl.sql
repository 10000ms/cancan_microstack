BEGIN;

CREATE TABLE caddy_route_tbl
(
    id BIGSERIAL PRIMARY KEY,
    
    -- 路由基本信息
    route_name VARCHAR(100) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    path_pattern VARCHAR(500) NOT NULL,
    
    -- 上游服务配置
    upstream_service VARCHAR(100) NOT NULL,
    upstream_host VARCHAR(100) NOT NULL,
    upstream_port INTEGER NOT NULL,
    
    -- 路由选项
    strip_path_prefix VARCHAR(200),
    add_path_prefix VARCHAR(200),
    enable_https BOOLEAN DEFAULT true,
    force_https BOOLEAN DEFAULT true,
    
    -- WAF 配置
    enable_waf BOOLEAN DEFAULT true,
    waf_rule_set VARCHAR(50) DEFAULT 'default',
    
    -- 负载均衡配置
    load_balance_strategy VARCHAR(50) DEFAULT 'round_robin',
    health_check_path VARCHAR(200),
    health_check_interval INTEGER DEFAULT 30,
    
    -- 状态和元数据
    is_enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,
    route_metadata JSONB DEFAULT '{}',
    description TEXT,
    
    -- 标准字段
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_caddy_route_tbl_route_name ON caddy_route_tbl (route_name);

-- 提升按更新时间查询效率
CREATE INDEX idx_caddy_route_tbl_update_time ON caddy_route_tbl (update_time);

-- 其他业务索引
CREATE INDEX idx_caddy_route_tbl_domain ON caddy_route_tbl (domain);
CREATE INDEX idx_caddy_route_tbl_upstream ON caddy_route_tbl (upstream_service);
CREATE INDEX idx_caddy_route_tbl_enabled ON caddy_route_tbl (is_enabled);
CREATE INDEX idx_caddy_route_tbl_priority ON caddy_route_tbl (priority);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_caddy_route_tbl
    BEFORE UPDATE
    ON caddy_route_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
