-- 执行审计日志表
-- Stores detailed logs for each attempt of a node instance execution.

BEGIN;

CREATE TABLE IF NOT EXISTS execution_log_tbl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_instance_id UUID NOT NULL REFERENCES node_instance_tbl(id),

    attempt_no INTEGER NOT NULL,

    -- Snapshots
    request_snapshot JSONB,
    response_snapshot JSONB,

    status VARCHAR(20), -- SUCCESS, FAILURE, TIMEOUT
    error_detail TEXT,

    -- Standard fields
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Execution-specific timestamps
    start_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMPTZ,
    duration_ms INTEGER
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exec_log_node_instance ON execution_log_tbl(node_instance_id);

-- 提升按更新时间查询效率
CREATE INDEX idx_execution_log_tbl_update_time ON execution_log_tbl (update_time);

-- Comments
COMMENT ON TABLE execution_log_tbl IS '执行审计日志表，记录每个节点实例每次尝试的详细日志';
COMMENT ON COLUMN execution_log_tbl.attempt_no IS '第几次尝试';
COMMENT ON COLUMN execution_log_tbl.request_snapshot IS '动作快照 (请求前)';
COMMENT ON COLUMN execution_log_tbl.response_snapshot IS '结果快照 (响应后)';
COMMENT ON COLUMN execution_log_tbl.status IS '执行结果状态: SUCCESS, FAILURE, TIMEOUT';
COMMENT ON COLUMN execution_log_tbl.flag IS '标志位 (0:正常, 1:已删除)';
COMMENT ON COLUMN execution_log_tbl.created_time IS '记录创建时间';
COMMENT ON COLUMN execution_log_tbl.update_time IS '记录最后更新时间';

COMMIT;
