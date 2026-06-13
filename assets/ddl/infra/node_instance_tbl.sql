-- 节点运行实例表
-- Stores each execution instance of a node within a workflow run.

BEGIN;

CREATE TABLE IF NOT EXISTS node_instance_tbl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_run_tbl(id),

    -- Corresponds to the key in the JSON graph (e.g. "step_1")
    node_id VARCHAR(50) NOT NULL,

    -- Loop iteration number (defaults to 1)
    loop_index INTEGER NOT NULL DEFAULT 1,

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    -- Data flow
    input_data JSONB DEFAULT '{}',   -- Input parameters for this node
    final_output JSONB DEFAULT '{}', -- Result produced by this node

    -- Statistics
    attempt_count INTEGER DEFAULT 0,
    error_msg TEXT,

    -- Standard fields
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_instance_unique ON node_instance_tbl(run_id, node_id, loop_index);
CREATE INDEX IF NOT EXISTS idx_node_instance_run_id ON node_instance_tbl(run_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_status ON node_instance_tbl(status);

-- 提升按更新时间查询效率
CREATE INDEX idx_node_instance_tbl_update_time ON node_instance_tbl (update_time);

-- Auto-update timestamp trigger
CREATE TRIGGER t_upd_node_instance_tbl
    BEFORE UPDATE ON node_instance_tbl
    FOR EACH ROW
    EXECUTE PROCEDURE upd_timestamp();

-- Comments
COMMENT ON TABLE node_instance_tbl IS '节点运行实例表，记录工作流中每个节点的执行状态';
COMMENT ON COLUMN node_instance_tbl.loop_index IS '循环轮次 (默认为 1)';
COMMENT ON COLUMN node_instance_tbl.input_data IS '进入该节点时的入参';
COMMENT ON COLUMN node_instance_tbl.final_output IS '该节点产出的结果';
COMMENT ON COLUMN node_instance_tbl.status IS '节点状态: PENDING, RUNNING, SUCCESS, FAILURE, SKIPPED, SUSPENDED, RETRYING, CANCELLED';
COMMENT ON COLUMN node_instance_tbl.flag IS '标志位 (0:正常, 1:已删除)';
COMMENT ON COLUMN node_instance_tbl.created_time IS '记录创建时间';
COMMENT ON COLUMN node_instance_tbl.update_time IS '记录最后更新时间';

COMMIT;
