-- 工作流定义表
-- Stores the definition of a workflow, including its graph structure and node configurations.

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_definition_tbl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Cron expression for scheduled runs
    schedule VARCHAR(100),

    -- UI data from the frontend (node coordinates, connections, etc.)
    graph_data JSONB DEFAULT '{}',

    global_context JSONB DEFAULT '{}',

    -- Core logic configuration (flattened map of nodes, keyed by node ID)
    nodes_config JSONB NOT NULL DEFAULT '{}',

    -- Whether the workflow is active (for scanner pickup)
    is_active BOOLEAN DEFAULT FALSE,

    -- Definition level versioning metadata
    version INTEGER NOT NULL DEFAULT 1,
    change_summary VARCHAR(255),

    -- Standard fields
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflow_def_active ON workflow_definition_tbl(is_active);
CREATE INDEX IF NOT EXISTS idx_workflow_def_schedule ON workflow_definition_tbl(schedule);

-- 提升按更新时间查询效率
CREATE INDEX idx_workflow_definition_tbl_update_time ON workflow_definition_tbl (update_time);

-- Auto-update timestamp trigger
CREATE TRIGGER t_upd_workflow_definition_tbl
    BEFORE UPDATE ON workflow_definition_tbl
    FOR EACH ROW
    EXECUTE PROCEDURE upd_timestamp();

-- Comments
COMMENT ON TABLE workflow_definition_tbl IS '工作流定义表，存储工作流的静态结构和配置';
COMMENT ON COLUMN workflow_definition_tbl.schedule IS '用于定时触发的 Cron 表达式';
COMMENT ON COLUMN workflow_definition_tbl.graph_data IS '前端 UI 数据 (节点坐标, 连线等)';
COMMENT ON COLUMN workflow_definition_tbl.nodes_config IS '核心逻辑配置 (扁平化的节点 Map, key为节点ID)。支持的节点类型: START, ACTION, TRANSFORM, LOGIC, FORK (并行分支), JOIN, LOOP, END';
COMMENT ON COLUMN workflow_definition_tbl.is_active IS '是否启用 (决定调度器是否扫描)';
COMMENT ON COLUMN workflow_definition_tbl.version IS '工作流定义版本号，配置变更时自增';
COMMENT ON COLUMN workflow_definition_tbl.change_summary IS '版本变更说明';
COMMENT ON COLUMN workflow_definition_tbl.flag IS '标志位 (0:正常, 1:已删除)';
COMMENT ON COLUMN workflow_definition_tbl.created_time IS '记录创建时间';
COMMENT ON COLUMN workflow_definition_tbl.update_time IS '记录最后更新时间';

COMMIT;
