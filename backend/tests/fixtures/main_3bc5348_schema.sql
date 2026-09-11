-- Frozen PostgreSQL schema compiled from backend/app/database/models.py at
-- main commit 3bc5348 (2025-12-24). Keep independent of current ORM metadata.
-- Includes original NOT NULL columns, client-only defaults, indexes and FKs.

CREATE TABLE client (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	email VARCHAR,
	phone VARCHAR,
	address VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE hunt (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	display_name VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	category VARCHAR NOT NULL,
	version VARCHAR NOT NULL,
	definition_json JSON,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_hunt_name ON hunt (name);

CREATE TABLE systemconfiguration (
	id SERIAL NOT NULL,
	case_number_template VARCHAR NOT NULL,
	case_number_prefix VARCHAR,
	api_keys JSON,
	evidence_folder_templates JSON,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE "user" (
	id SERIAL NOT NULL,
	username VARCHAR NOT NULL,
	email VARCHAR NOT NULL,
	password_hash VARCHAR NOT NULL,
	role VARCHAR NOT NULL,
	is_active BOOLEAN NOT NULL,
	is_superadmin BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_user_email ON "user" (email);

CREATE UNIQUE INDEX ix_user_username ON "user" (username);

CREATE TABLE "case" (
	id SERIAL NOT NULL,
	client_id INTEGER,
	case_number VARCHAR NOT NULL,
	title VARCHAR,
	status VARCHAR NOT NULL,
	notes VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(client_id) REFERENCES client (id)
);

CREATE TABLE invite (
	id SERIAL NOT NULL,
	token VARCHAR NOT NULL,
	role VARCHAR NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	used_at TIMESTAMP WITHOUT TIME ZONE,
	created_by_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (token),
	FOREIGN KEY(created_by_id) REFERENCES "user" (id)
);

CREATE TABLE tasktemplate (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	display_name VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	category VARCHAR NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_by_id INTEGER,
	definition_json JSON,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by_id) REFERENCES "user" (id)
);

CREATE UNIQUE INDEX ix_tasktemplate_name ON tasktemplate (name);

CREATE TABLE caseuserlink (
	case_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	is_lead BOOLEAN NOT NULL,
	PRIMARY KEY (case_id, user_id),
	FOREIGN KEY(case_id) REFERENCES "case" (id),
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE entity (
	id SERIAL NOT NULL,
	case_id INTEGER NOT NULL,
	entity_type VARCHAR NOT NULL,
	data JSON,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	created_by_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(case_id) REFERENCES "case" (id),
	FOREIGN KEY(created_by_id) REFERENCES "user" (id)
);

CREATE INDEX ix_entity_entity_type ON entity (entity_type);

CREATE TABLE evidence (
	id SERIAL NOT NULL,
	case_id INTEGER NOT NULL,
	title VARCHAR NOT NULL,
	description VARCHAR,
	evidence_type VARCHAR NOT NULL,
	category VARCHAR NOT NULL,
	content VARCHAR NOT NULL,
	file_hash VARCHAR(64),
	folder_path VARCHAR(500),
	is_folder BOOLEAN NOT NULL,
	parent_folder_id INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	created_by_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(case_id) REFERENCES "case" (id),
	FOREIGN KEY(parent_folder_id) REFERENCES evidence (id),
	FOREIGN KEY(created_by_id) REFERENCES "user" (id)
);

CREATE TABLE huntexecution (
	id SERIAL NOT NULL,
	hunt_id INTEGER NOT NULL,
	case_id INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	progress FLOAT NOT NULL,
	initial_parameters JSON,
	context_data JSON,
	started_at TIMESTAMP WITHOUT TIME ZONE,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	created_by_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(hunt_id) REFERENCES hunt (id),
	FOREIGN KEY(case_id) REFERENCES "case" (id),
	FOREIGN KEY(created_by_id) REFERENCES "user" (id)
);

CREATE TABLE task (
	id SERIAL NOT NULL,
	case_id INTEGER NOT NULL,
	template_id INTEGER,
	title VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	priority VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	assigned_to_id INTEGER,
	assigned_by_id INTEGER NOT NULL,
	due_date TIMESTAMP WITHOUT TIME ZONE,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	completed_by_id INTEGER,
	custom_fields JSON,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(case_id) REFERENCES "case" (id),
	FOREIGN KEY(template_id) REFERENCES tasktemplate (id),
	FOREIGN KEY(assigned_to_id) REFERENCES "user" (id),
	FOREIGN KEY(assigned_by_id) REFERENCES "user" (id),
	FOREIGN KEY(completed_by_id) REFERENCES "user" (id)
);

CREATE TABLE huntstep (
	id SERIAL NOT NULL,
	execution_id INTEGER NOT NULL,
	step_id VARCHAR NOT NULL,
	plugin_name VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	parameters JSON,
	output JSON,
	error_details VARCHAR,
	retry_count INTEGER NOT NULL,
	started_at TIMESTAMP WITHOUT TIME ZONE,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(execution_id) REFERENCES huntexecution (id)
);
