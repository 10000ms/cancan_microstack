-- 工作流运行实例表
-- Stores each execution instance of a workflow.

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_run_tbl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definition_tbl(id),

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    -- Trigger source information
    trigger_type VARCHAR(20) NOT NULL,
    trigger_context JSONB DEFAULT '{}',

    -- Global context data that flows through the workflow
    global_context JSONB DEFAULT '{}',

    -- Definition snapshot metadata to guarantee immutable runs
    definition_version INTEGER,
    definition_snapshot JSONB,

    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Standard fields
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflow_run_workflow_id ON workflow_run_tbl(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_run_status ON workflow_run_tbl(status);

-- 提升按更新时间查询效率
CREATE INDEX idx_workflow_run_tbl_update_time ON workflow_run_tbl (update_time);

-- Comments
COMMENT ON TABLE workflow_run_tbl IS '工作流运行实例表';
COMMENT ON COLUMN workflow_run_tbl.trigger_type IS '触发类型: MANUAL, SCHEDULE, API';
COMMENT ON COLUMN workflow_run_tbl.trigger_context IS '触发时的元数据';
COMMENT ON COLUMN workflow_run_tbl.global_context IS '全局上下文数据 (随流程流动)';
COMMENT ON COLUMN workflow_run_tbl.definition_version IS '触发时绑定的定义版本号 / Definition version captured when triggering';
COMMENT ON COLUMN workflow_run_tbl.definition_snapshot IS '触发时的完整工作流定义快照 / Serialized workflow definition snapshot captured at trigger time';
COMMENT ON COLUMN workflow_run_tbl.status IS '运行状态: PENDING, RUNNING, SUCCESS, FAILURE, CANCELLED, PAUSED';
COMMENT ON COLUMN workflow_run_tbl.flag IS '标志位 (0:正常, 1:已删除)';
COMMENT ON COLUMN workflow_run_tbl.created_time IS '记录创建时间';
COMMENT ON COLUMN workflow_run_tbl.update_time IS '记录最后更新时间';

COMMIT;