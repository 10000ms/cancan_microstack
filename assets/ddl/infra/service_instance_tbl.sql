BEGIN;

-- 服务实例表：记录所有服务实例的详细信息和状态
-- Service Instance Table: Records detailed info and status of all service instances
CREATE TABLE service_instance_tbl
(
    id                    BIGSERIAL PRIMARY KEY,
    service_name          VARCHAR(100)             NOT NULL,
    instance_id           VARCHAR(64)              NOT NULL,
    container_name        VARCHAR(100)             DEFAULT '', -- 允许为空，非容器环境可能没有
    compose_service_name  VARCHAR(100)             DEFAULT '',
    host                  VARCHAR(100)             NOT NULL,
    port                  INTEGER                  NOT NULL,
    internal_port         INTEGER                  NOT NULL DEFAULT 8080,
    status                VARCHAR(20)              NOT NULL DEFAULT 'UP', -- UP, DOWN, STARTING, etc.
    expected_status       VARCHAR(20)              DEFAULT 'UP',          -- 期望状态 / Expected status
    health_check_url      VARCHAR(255),                                   -- 健康检查 URL (实例级)
    health_status         VARCHAR(20)              DEFAULT 'unknown',     -- healthy, unhealthy, unknown
    last_health_check     TIMESTAMP WITH TIME ZONE,
    last_heartbeat        TIMESTAMP WITH TIME ZONE,                       -- 最后心跳时间
    consecutive_failures  SMALLINT                 DEFAULT 0,
    last_health_error     TEXT,
    started_at            TIMESTAMP WITH TIME ZONE,
    stopped_at            TIMESTAMP WITH TIME ZONE,
    restart_count         INT                      DEFAULT 0,
    cpu_limit             VARCHAR,
    memory_limit          VARCHAR,
    instance_metadata     JSONB                    DEFAULT '{}'::JSONB,
    flag                  SMALLINT                 DEFAULT 0,
    created_time          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引：实例ID全局唯一
CREATE UNIQUE INDEX uk_service_instance_tbl_instance_id ON service_instance_tbl (instance_id);

-- 复合索引：服务维度的实例查询
CREATE INDEX idx_service_instance_tbl_service_instance ON service_instance_tbl (service_name, instance_id);

-- 状态/健康索引，便于统计聚合
CREATE INDEX idx_service_instance_tbl_status ON service_instance_tbl (service_name, status);
CREATE INDEX idx_service_instance_tbl_health_status ON service_instance_tbl (service_name, health_status);

-- 心跳索引 (用于清理过期实例)
CREATE INDEX idx_service_instance_tbl_last_heartbeat ON service_instance_tbl (service_name, last_heartbeat);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_service_instance_tbl
    BEFORE UPDATE
    ON service_instance_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
