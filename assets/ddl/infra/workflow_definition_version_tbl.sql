BEGIN;

-- 工作流定义版本快照表 / Workflow definition history table
CREATE TABLE IF NOT EXISTS workflow_definition_version_tbl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definition_tbl(id),
    version INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    schedule VARCHAR(100),
    graph_data JSONB DEFAULT '{}',
    nodes_config JSONB NOT NULL DEFAULT '{}',
    global_context JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    change_summary VARCHAR(255),

    -- Standard fields
    flag SMALLINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_workflow_definition_version_tbl ON workflow_definition_version_tbl(workflow_id, version);

-- Auto-update timestamp trigger
CREATE TRIGGER t_upd_workflow_definition_version_tbl
    BEFORE UPDATE ON workflow_definition_version_tbl
    FOR EACH ROW
    EXECUTE PROCEDURE upd_timestamp();

COMMENT ON TABLE workflow_definition_version_tbl IS '工作流版本快照表，记录每次发布或回滚后的定义快照';
COMMENT ON COLUMN workflow_definition_version_tbl.version IS '对应 workflow_definition_tbl 的版本号';
COMMENT ON COLUMN workflow_definition_version_tbl.change_summary IS '版本变更说明（回滚/发布原因）';

COMMIT;
