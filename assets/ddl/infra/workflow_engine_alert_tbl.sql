BEGIN;

CREATE TABLE workflow_engine_alert_tbl
(
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID REFERENCES workflow_run_tbl (id),
    node_id          VARCHAR(64)                     NOT NULL,
    loop_index       INTEGER                         NOT NULL DEFAULT 1,
    severity         VARCHAR(16)                     NOT NULL,
    category         VARCHAR(32)                     NOT NULL,
    reason           VARCHAR(255)                    NOT NULL,
    detail           JSONB,
    status           VARCHAR(16)                     NOT NULL DEFAULT 'OPEN',
    acknowledged_by  VARCHAR(64),
    acknowledged_at  TIMESTAMP WITH TIME ZONE,
    resolved_by      VARCHAR(64),
    resolved_at      TIMESTAMP WITH TIME ZONE,
    note             TEXT,
    flag             SMALLINT                         DEFAULT 0,
    created_time     TIMESTAMP WITH TIME ZONE         DEFAULT CURRENT_TIMESTAMP,
    update_time      TIMESTAMP WITH TIME ZONE         DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_engine_alert_tbl_status ON workflow_engine_alert_tbl (status);
CREATE INDEX idx_workflow_engine_alert_tbl_run ON workflow_engine_alert_tbl (run_id);
CREATE INDEX idx_workflow_engine_alert_tbl_created ON workflow_engine_alert_tbl (created_time DESC);

CREATE TRIGGER t_upd_workflow_engine_alert_tbl
    BEFORE UPDATE
    ON workflow_engine_alert_tbl
    FOR EACH ROW
EXECUTE PROCEDURE upd_timestamp();

COMMIT;
