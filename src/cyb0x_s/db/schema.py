"""SQLite schema definition for CYB0X-S (Safe Field Notebook).

Local-first, relational integrity, zero network dependencies.
"""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL DEFAULT 1,
    ip TEXT NOT NULL,
    hostname TEXT DEFAULT '',
    os TEXT DEFAULT 'Unknown',
    notes TEXT DEFAULT '',
    initial_access_vuln TEXT DEFAULT '',
    foothold_cmd TEXT DEFAULT '',
    foothold_context TEXT DEFAULT '',
    privesc_vector TEXT DEFAULT '',
    root_proof TEXT DEFAULT '',
    user_flag TEXT DEFAULT '',
    root_flag TEXT DEFAULT '',
    subnet TEXT DEFAULT '',
    is_pivot INTEGER DEFAULT 0,
    pivot_route TEXT DEFAULT '',
    is_in_scope INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    UNIQUE(workspace_id, ip)
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'tcp',
    service TEXT NOT NULL DEFAULT 'unknown',
    version TEXT DEFAULT '',
    access_potential TEXT DEFAULT '',
    next_action TEXT DEFAULT '',
    status TEXT DEFAULT 'CHECKED',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE,
    UNIQUE(target_id, port, protocol)
);

CREATE TABLE IF NOT EXISTS failure_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    where_stuck TEXT DEFAULT '',
    breakthrough_clue TEXT DEFAULT '',
    rule_for_next_time TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    severity TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    username TEXT NOT NULL,
    secret TEXT NOT NULL,
    source TEXT DEFAULT '',
    service_scope TEXT DEFAULT '',
    status TEXT DEFAULT 'untested',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    evidence_type TEXT DEFAULT 'screenshot',
    path_or_ref TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    category TEXT DEFAULT 'ENUMERATION',
    title TEXT NOT NULL,
    status TEXT DEFAULT 'TODO',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    command TEXT NOT NULL,
    notes TEXT DEFAULT '',
    is_golden INTEGER DEFAULT 0,
    step TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cred_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT '○ UNTESTED',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(credential_id) REFERENCES credentials(id) ON DELETE CASCADE,
    FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE,
    UNIQUE(credential_id, service_id)
);

CREATE TABLE IF NOT EXISTS exam_proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    question_num TEXT NOT NULL,
    category TEXT DEFAULT 'FLAG',
    answer_proof TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

-- Indices for rapid search, foreign key cascade verification, and status retrieval
CREATE INDEX IF NOT EXISTS idx_targets_ws ON targets(workspace_id);
CREATE INDEX IF NOT EXISTS idx_services_target ON services(target_id);
CREATE INDEX IF NOT EXISTS idx_findings_target ON findings(target_id);
CREATE INDEX IF NOT EXISTS idx_creds_target ON credentials(target_id);
CREATE INDEX IF NOT EXISTS idx_checklist_target ON checklist(target_id);
CREATE INDEX IF NOT EXISTS idx_checklist_target_status ON checklist(target_id, status);
CREATE INDEX IF NOT EXISTS idx_notes_target ON notes(target_id);
CREATE INDEX IF NOT EXISTS idx_leads_target ON leads(target_id);
CREATE INDEX IF NOT EXISTS idx_evidence_target ON evidence(target_id);
CREATE INDEX IF NOT EXISTS idx_failure_log_target ON failure_log(target_id);
CREATE INDEX IF NOT EXISTS idx_command_history_target ON command_history(target_id);
CREATE INDEX IF NOT EXISTS idx_cred_validations ON cred_validations(credential_id, service_id);
CREATE INDEX IF NOT EXISTS idx_cred_validations_service ON cred_validations(service_id);
CREATE INDEX IF NOT EXISTS idx_exam_proofs_q ON exam_proofs(question_num);
CREATE INDEX IF NOT EXISTS idx_exam_proofs_target ON exam_proofs(target_id);

-- FTS5 Full-Text Search Virtual Table and Automatic Synchronization Triggers
CREATE VIRTUAL TABLE IF NOT EXISTS notebook_fts USING fts5(
    entity_type,
    entity_id UNINDEXED,
    target_id UNINDEXED,
    title,
    content,
    tags,
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers for automatic FTS indexing
CREATE TRIGGER IF NOT EXISTS trg_notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('note', new.id, new.target_id, 'Field Note', new.content, 'note');
END;
CREATE TRIGGER IF NOT EXISTS trg_notes_ad AFTER DELETE ON notes BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'note' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_notes_au AFTER UPDATE ON notes BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'note' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('note', new.id, new.target_id, 'Field Note', new.content, 'note');
END;

CREATE TRIGGER IF NOT EXISTS trg_targets_ai AFTER INSERT ON targets BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('target', new.id, new.id, 'Target: ' || new.ip || ' (' || coalesce(new.hostname, 'no host') || ')', 'OS: ' || coalesce(new.os, '') || ' | Notes: ' || coalesce(new.notes, '') || ' | Vuln: ' || coalesce(new.initial_access_vuln, '') || ' | Foothold: ' || coalesce(new.foothold_cmd, '') || ' | PrivEsc: ' || coalesce(new.privesc_vector, '') || ' | Root: ' || coalesce(new.root_proof, '') || ' | Flags: ' || coalesce(new.user_flag, '') || ' ' || coalesce(new.root_flag, ''), coalesce(new.subnet, ''));
END;
CREATE TRIGGER IF NOT EXISTS trg_targets_ad AFTER DELETE ON targets BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'target' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_targets_au AFTER UPDATE ON targets BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'target' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('target', new.id, new.id, 'Target: ' || new.ip || ' (' || coalesce(new.hostname, 'no host') || ')', 'OS: ' || coalesce(new.os, '') || ' | Notes: ' || coalesce(new.notes, '') || ' | Vuln: ' || coalesce(new.initial_access_vuln, '') || ' | Foothold: ' || coalesce(new.foothold_cmd, '') || ' | PrivEsc: ' || coalesce(new.privesc_vector, '') || ' | Root: ' || coalesce(new.root_proof, '') || ' | Flags: ' || coalesce(new.user_flag, '') || ' ' || coalesce(new.root_flag, ''), coalesce(new.subnet, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_services_ai AFTER INSERT ON services BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('service', new.id, new.target_id, 'Service: ' || new.port || '/' || new.protocol || ' ' || new.service, 'Version: ' || coalesce(new.version, '') || ' [' || new.status || '] ' || coalesce(new.notes, '') || ' ' || coalesce(new.next_action, ''), coalesce(new.service, ''));
END;
CREATE TRIGGER IF NOT EXISTS trg_services_ad AFTER DELETE ON services BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'service' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_services_au AFTER UPDATE ON services BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'service' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('service', new.id, new.target_id, 'Service: ' || new.port || '/' || new.protocol || ' ' || new.service, 'Version: ' || coalesce(new.version, '') || ' [' || new.status || '] ' || coalesce(new.notes, '') || ' ' || coalesce(new.next_action, ''), coalesce(new.service, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_findings_ai AFTER INSERT ON findings BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('finding', new.id, new.target_id, 'Finding: ' || new.title, coalesce(new.description, '') || ' ' || coalesce(new.notes, ''), coalesce(new.severity, 'info'));
END;
CREATE TRIGGER IF NOT EXISTS trg_findings_ad AFTER DELETE ON findings BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'finding' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_findings_au AFTER UPDATE ON findings BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'finding' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('finding', new.id, new.target_id, 'Finding: ' || new.title, coalesce(new.description, '') || ' ' || coalesce(new.notes, ''), coalesce(new.severity, 'info'));
END;

CREATE TRIGGER IF NOT EXISTS trg_credentials_ai AFTER INSERT ON credentials BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('credential', new.id, new.target_id, 'Credential: ' || new.username || ' : ********', 'Scope: ' || coalesce(new.service_scope, 'GLOBAL') || ' | Source: ' || coalesce(new.source, '') || ' [' || new.status || '] ' || coalesce(new.notes, ''), coalesce(new.service_scope, ''));
END;
CREATE TRIGGER IF NOT EXISTS trg_credentials_ad AFTER DELETE ON credentials BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'credential' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_credentials_au AFTER UPDATE ON credentials BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'credential' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('credential', new.id, new.target_id, 'Credential: ' || new.username || ' : ********', 'Scope: ' || coalesce(new.service_scope, 'GLOBAL') || ' | Source: ' || coalesce(new.source, '') || ' [' || new.status || '] ' || coalesce(new.notes, ''), coalesce(new.service_scope, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_checklist_ai AFTER INSERT ON checklist BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('checklist', new.id, new.target_id, 'Checklist [' || new.status || ']: ' || new.title, 'Category: ' || new.category || ' ' || coalesce(new.notes, ''), new.status);
END;
CREATE TRIGGER IF NOT EXISTS trg_checklist_ad AFTER DELETE ON checklist BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'checklist' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_checklist_au AFTER UPDATE ON checklist BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'checklist' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('checklist', new.id, new.target_id, 'Checklist [' || new.status || ']: ' || new.title, 'Category: ' || new.category || ' ' || coalesce(new.notes, ''), new.status);
END;

CREATE TRIGGER IF NOT EXISTS trg_evidence_ai AFTER INSERT ON evidence BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('evidence', new.id, new.target_id, 'Evidence (' || new.evidence_type || '): ' || new.path_or_ref, coalesce(new.description, ''), new.evidence_type);
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_ad AFTER DELETE ON evidence BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'evidence' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_au AFTER UPDATE ON evidence BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'evidence' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('evidence', new.id, new.target_id, 'Evidence (' || new.evidence_type || '): ' || new.path_or_ref, coalesce(new.description, ''), new.evidence_type);
END;

CREATE TRIGGER IF NOT EXISTS trg_commands_ai AFTER INSERT ON command_history BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('command', new.id, new.target_id, 'Command: ' || new.command, 'Step: ' || coalesce(new.step, '') || ' | ' || coalesce(new.notes, ''), case when new.is_golden = 1 then 'golden' else 'cmd' end);
END;
CREATE TRIGGER IF NOT EXISTS trg_commands_ad AFTER DELETE ON command_history BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'command' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_commands_au AFTER UPDATE ON command_history BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'command' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('command', new.id, new.target_id, 'Command: ' || new.command, 'Step: ' || coalesce(new.step, '') || ' | ' || coalesce(new.notes, ''), case when new.is_golden = 1 then 'golden' else 'cmd' end);
END;

CREATE TRIGGER IF NOT EXISTS trg_leads_ai AFTER INSERT ON leads BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('lead', new.id, new.target_id, 'Lead: ' || new.title, 'Status: ' || new.status || ' | ' || coalesce(new.notes, ''), new.status);
END;
CREATE TRIGGER IF NOT EXISTS trg_leads_ad AFTER DELETE ON leads BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'lead' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_leads_au AFTER UPDATE ON leads BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'lead' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('lead', new.id, new.target_id, 'Lead: ' || new.title, 'Status: ' || new.status || ' | ' || coalesce(new.notes, ''), new.status);
END;

CREATE TRIGGER IF NOT EXISTS trg_proofs_ai AFTER INSERT ON exam_proofs BEGIN
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('proof', new.id, new.target_id, 'Objective [' || new.question_num || ']: ' || new.category, 'Proof: ' || new.answer_proof || ' | ' || coalesce(new.notes, ''), new.category);
END;
CREATE TRIGGER IF NOT EXISTS trg_proofs_ad AFTER DELETE ON exam_proofs BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'proof' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_proofs_au AFTER UPDATE ON exam_proofs BEGIN
    DELETE FROM notebook_fts WHERE entity_type = 'proof' AND entity_id = old.id;
    INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
    VALUES ('proof', new.id, new.target_id, 'Objective [' || new.question_num || ']: ' || new.category, 'Proof: ' || new.answer_proof || ' | ' || coalesce(new.notes, ''), new.category);
END;
"""
