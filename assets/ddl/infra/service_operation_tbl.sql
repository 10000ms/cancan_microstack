BEGIN;

CREATE TABLE service_operation_tbl
(
    id                BIGSERIAL PRIMARY KEY,
    operation_id      VARCHAR                  NOT NULL,
    operation_type    VARCHAR(20)              NOT NULL,
    service_name      VARCHAR(100)             NOT NULL,
    operation_params  JSONB                    DEFAULT '{}',
    status            VARCHAR(20)              NOT NULL,
    started_at        TIMESTAMP WITH TIME ZONE,
    completed_at      TIMESTAMP WITH TIME ZONE,
    result            JSONB                    DEFAULT '{}',
    error_message     TEXT,
    retry_count       SMALLINT                 DEFAULT 0,
    max_retries       SMALLINT                 DEFAULT 3,
    last_retry_at     TIMESTAMP WITH TIME ZONE,
    initiated_by      VARCHAR(100),
    initiated_from    VARCHAR(100),
    flag              SMALLINT                 DEFAULT 0,
    created_time      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_service_operation_tbl_operation_id ON service_operation_tbl (operation_id);

-- 提升按更新时间查询效率
CREATE INDEX idx_service_operation_tbl_update_time ON service_operation_tbl (update_time);

-- 服务操作查询索引 (用于查询特定服务的操作历史)
CREATE INDEX idx_service_operation_tbl_service_operation ON service_operation_tbl (service_name, operation_type, status);

-- 状态和时间索引 (用于查询待处理/超时的操作)
CREATE INDEX idx_service_operation_tbl_status_created ON service_operation_tbl (status, created_time);

-- 时间范围查询索引 (用于清理历史数据)
CREATE INDEX idx_service_operation_tbl_created_time ON service_operation_tbl (created_time DESC);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_service_operation_tbl
    BEFORE UPDATE
    ON service_operation_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
