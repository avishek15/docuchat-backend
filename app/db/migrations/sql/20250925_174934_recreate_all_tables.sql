-- Auto-generated migration: 20250925_174934
-- Generated from SQLModel classes using SQLAlchemy
-- WARNING: This will DROP all existing tables and recreate them

-- Step 1: Drop existing tables
DROP TABLE IF EXISTS file_chunks;
DROP TABLE IF EXISTS files;
DROP TABLE IF EXISTS user_sessions;
DROP TABLE IF EXISTS users;

-- Step 2: Create tables from SQLModel definitions

CREATE TABLE users (
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	id INTEGER NOT NULL, 
	email VARCHAR NOT NULL, 
	name VARCHAR(255), 
	ip_address VARCHAR, 
	status VARCHAR NOT NULL, 
	last_accessed DATETIME, 
	PRIMARY KEY (id)
)

;

CREATE TABLE user_sessions (
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token VARCHAR NOT NULL, 
	ip_address VARCHAR NOT NULL, 
	expires_at DATETIME NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE TABLE files (
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	id INTEGER NOT NULL, 
	file_id VARCHAR NOT NULL, 
	user_id INTEGER NOT NULL, 
	file_name VARCHAR NOT NULL, 
	file_size INTEGER NOT NULL, 
	file_type VARCHAR, 
	content_hash VARCHAR, 
	storage_path VARCHAR, 
	status VARCHAR NOT NULL, 
	processed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE TABLE file_chunks (
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	id INTEGER NOT NULL, 
	file_id INTEGER NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	content VARCHAR NOT NULL, 
	embedding_id VARCHAR, 
	token_count INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(file_id) REFERENCES files (id)
)

;

-- Step 3: Create migrations tracking table
CREATE TABLE IF NOT EXISTS migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO migrations (version, description) 
VALUES ('20250925_174934', 'Auto-generated from SQLModel classes');
