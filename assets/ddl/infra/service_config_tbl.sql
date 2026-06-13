BEGIN;

CREATE TABLE service_config_tbl
(
    id           BIGSERIAL PRIMARY KEY,
    service_name VARCHAR NOT NULL,
    conf_key     VARCHAR NOT NULL,
    conf_value   TEXT,
    flag         SMALLINT                 DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uk_service_config_tbl_service_name_conf_key ON service_config_tbl (service_name, conf_key);

-- 提升按更新时间查询效率
CREATE INDEX idx_service_config_tbl_update_time ON service_config_tbl (update_time);

-- 自动更新时间戳触发器
CREATE TRIGGER t_upd_service_config_tbl
    BEFORE UPDATE
    ON service_config_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
