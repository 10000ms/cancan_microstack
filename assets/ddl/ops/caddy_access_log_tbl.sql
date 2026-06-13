BEGIN;

CREATE TABLE caddy_access_log_tbl
(
    id BIGSERIAL PRIMARY KEY,
    
    -- 请求基本信息
    request_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 客户端信息
    client_ip VARCHAR(50) NOT NULL,                        -- 客户端 IP
    client_port INTEGER,                                   -- 客户端端口
    user_agent TEXT,                                       -- User-Agent
    referer TEXT,                                          -- Referer
    
    -- IP 地理位置信息（使用 IP 库解析）
    country VARCHAR(100),                                  -- 国家
    country_code VARCHAR(10),                              -- 国家代码（如 CN, US）
    region VARCHAR(100),                                   -- 省份/州
    city VARCHAR(100),                                     -- 城市
    latitude DECIMAL(10, 8),                               -- 纬度
    longitude DECIMAL(11, 8),                              -- 经度
    timezone VARCHAR(50),                                  -- 时区
    isp VARCHAR(200),                                      -- ISP 运营商
    
    -- 请求信息
    method VARCHAR(10) NOT NULL,                           -- HTTP 方法（GET/POST 等）
    protocol VARCHAR(20),                                  -- 协议版本（HTTP/1.1, HTTP/2）
    host VARCHAR(255),                                     -- 请求的 Host
    path TEXT NOT NULL,                                    -- 请求路径
    query_string TEXT,                                     -- 查询字符串
    
    -- 路由和服务信息
    matched_route VARCHAR(100),                            -- 匹配的路由名称
    upstream_service VARCHAR(100),                         -- 转发到的上游服务
    upstream_host VARCHAR(100),                            -- 上游服务主机
    upstream_port INTEGER,                                 -- 上游服务端口
    
    -- 响应信息
    status_code INTEGER NOT NULL,                          -- HTTP 状态码
    response_size BIGINT,                                  -- 响应大小（字节）
    response_time INTEGER,                                 -- 响应时间（毫秒）
    
    -- WAF 信息
    waf_action VARCHAR(50),                                -- WAF 动作（allow/block/log）
    waf_rule_id VARCHAR(100),                              -- 触发的 WAF 规则 ID
    waf_score INTEGER,                                     -- WAF 威胁评分
    
    -- 限流信息
    rate_limited BOOLEAN DEFAULT false,                    -- 是否被限流
    rate_limit_rule VARCHAR(100),                          -- 限流规则名称
    
    -- TLS 信息
    tls_version VARCHAR(20),                               -- TLS 版本
    tls_cipher VARCHAR(100),                               -- TLS 加密套件
    
    -- 元数据
    log_metadata JSONB DEFAULT '{}',
    
    -- 标准字段
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_caddy_access_log_tbl_request_id ON caddy_access_log_tbl (request_id);

-- 提升按更新时间查询效率
CREATE INDEX idx_caddy_access_log_tbl_update_time ON caddy_access_log_tbl (update_time);

-- 优化查询性能的索引
CREATE INDEX idx_caddy_access_log_tbl_timestamp ON caddy_access_log_tbl (timestamp DESC);
CREATE INDEX idx_caddy_access_log_tbl_client_ip ON caddy_access_log_tbl (client_ip);
CREATE INDEX idx_caddy_access_log_tbl_status_code ON caddy_access_log_tbl (status_code);
CREATE INDEX idx_caddy_access_log_tbl_upstream_service ON caddy_access_log_tbl (upstream_service);
CREATE INDEX idx_caddy_access_log_tbl_country ON caddy_access_log_tbl (country);

-- 复合索引（优化常见查询）
CREATE INDEX idx_caddy_access_log_tbl_service_time ON caddy_access_log_tbl (upstream_service, timestamp DESC);
CREATE INDEX idx_caddy_access_log_tbl_ip_time ON caddy_access_log_tbl (client_ip, timestamp DESC);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_caddy_access_log_tbl
    BEFORE UPDATE
    ON caddy_access_log_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
