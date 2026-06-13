-- 服务行为日志表（service_action_log_tbl）
-- 记录服务实例的所有关键行为：上线、下线、重启、扩缩容等

CREATE TABLE IF NOT EXISTS service_action_log_tbl (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,          -- 服务名称
    instance_id VARCHAR(50),                     -- 实例ID（可为空，如果是服务级别操作）
    action_type VARCHAR(50) NOT NULL,            -- 行为类型：register, deregister, heartbeat, health_check_fail, restart, scale, rebuild
    action_status VARCHAR(20) NOT NULL,          -- 行为状态：success, failed, in_progress
    action_detail JSONB DEFAULT '{}',            -- 行为详情（JSON格式）
    error_message TEXT,                          -- 错误信息（如果失败）
    triggered_by VARCHAR(50) DEFAULT 'system',   -- 触发者：system, user, auto
    action_metadata JSONB DEFAULT '{}',          -- 行为附加元数据
    flag SMALLINT DEFAULT 0,                     -- 标志位
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_service_action_log_service_name ON service_action_log_tbl(service_name);
CREATE INDEX idx_service_action_log_instance_id ON service_action_log_tbl(instance_id);
CREATE INDEX idx_service_action_log_action_type ON service_action_log_tbl(action_type);
CREATE INDEX idx_service_action_log_action_status ON service_action_log_tbl(action_status);
CREATE INDEX idx_service_action_log_created_time ON service_action_log_tbl(created_time DESC);

-- 添加更新时间触发器
CREATE TRIGGER update_service_action_log_update_time
    BEFORE UPDATE ON service_action_log_tbl
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- 添加注释
COMMENT ON TABLE service_action_log_tbl IS '服务行为日志表，记录服务实例的所有关键行为';
COMMENT ON COLUMN service_action_log_tbl.action_type IS '行为类型：register(注册), deregister(注销), heartbeat(心跳), health_check_fail(健康检查失败), restart(重启), scale(扩缩容), rebuild(重建)';
COMMENT ON COLUMN service_action_log_tbl.action_status IS '行为状态：success(成功), failed(失败), in_progress(进行中)';
COMMENT ON COLUMN service_action_log_tbl.triggered_by IS '触发者：system(系统自动), user(用户手动), auto(自动化策略)';
