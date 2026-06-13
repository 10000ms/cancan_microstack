BEGIN;

CREATE TABLE service_info_tbl
(
    id                BIGSERIAL PRIMARY KEY,
    service_name      VARCHAR(100)             NOT NULL,
    description       TEXT,
    service_type      VARCHAR(50)              DEFAULT 'business',
    health_check_path VARCHAR(255)             DEFAULT '/internal/health',
    service_metadata  JSONB                    DEFAULT '{}',
    expected_status   VARCHAR(20)              DEFAULT 'running',
    desired_replicas  SMALLINT                 DEFAULT 1,
    actual_replicas   SMALLINT                 DEFAULT 0,
    last_scale_at     TIMESTAMP WITH TIME ZONE,
    scale_policy      JSONB                    DEFAULT '{}',
    registered_time   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_registered_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    flag              SMALLINT                 DEFAULT 0,
    created_time      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 唯一索引
CREATE UNIQUE INDEX uk_service_info_tbl_service_name ON service_info_tbl (service_name);

-- 提升按更新时间查询效率
CREATE INDEX idx_service_info_tbl_update_time ON service_info_tbl (update_time);

-- 服务类型索引
CREATE INDEX idx_service_info_tbl_service_type ON service_info_tbl (service_type);

-- 标志位索引
CREATE INDEX idx_service_info_tbl_flag ON service_info_tbl (flag);

-- 期望状态索引
CREATE INDEX idx_service_info_tbl_expected_status ON service_info_tbl (expected_status);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_service_info_tbl
    BEFORE UPDATE
    ON service_info_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
