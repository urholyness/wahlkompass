-- v1.1 Init Migration Schema
-- Scope: Germany first, Country-agnostic core database mapping

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Country table
CREATE TABLE country (
    code          CHAR(3) PRIMARY KEY,                  -- ISO 3166-1 alpha-3: DEU, KEN, NLD ...
    name          TEXT NOT NULL
);

-- Legislature table
CREATE TABLE legislature (
    id            SERIAL PRIMARY KEY,
    country_code  CHAR(3) NOT NULL REFERENCES country(code),
    name          TEXT NOT NULL,                        -- Bundestag, Landtag NRW ...
    level         TEXT NOT NULL CHECK (level IN ('national', 'regional', 'local')),
    seats         INT NOT NULL,
    majority      INT NOT NULL
);

-- Policy objects (A3 amendment)
CREATE TABLE policy (
    id            SERIAL PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,                 -- e.g. 'schuldenbremse-de'
    name_de       TEXT NOT NULL,
    aliases       TEXT[],                               -- For entity linking/search
    topic         TEXT NOT NULL                         -- General policy area
);

-- Party profiles
CREATE TABLE party (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    short_name    TEXT NOT NULL,
    level         TEXT NOT NULL DEFAULT 'federal',      -- federal | land:BY | land:NW ...
    ballot_status TEXT NOT NULL CHECK (ballot_status IN ('admitted', 'parliamentary', 'historical')),
    color_hex     CHAR(7) NOT NULL DEFAULT '#7F7F7F',   -- Party color hex value
    UNIQUE (short_name, level)
);

-- Election table
CREATE TABLE election (
    id            SERIAL PRIMARY KEY,
    legislature_id INT NOT NULL REFERENCES legislature(id),
    name          TEXT NOT NULL,                        -- Bundestagswahl 2025
    election_date DATE NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('draft', 'active', 'completed'))
);

-- Statements
CREATE TABLE statement (
    id            SERIAL PRIMARY KEY,
    election_id   INT NOT NULL REFERENCES election(id),
    policy_id     INT REFERENCES policy(id),            -- Reference to persistent policy object
    text_de       TEXT NOT NULL,
    text_easy_de  TEXT,                                 -- Plain-language version (Leichte Sprache)
    context_de    TEXT,                                 -- Neutral context context description
    topic         TEXT NOT NULL,                        -- Topic rubric bucket (for balance audit)
    admission_ref TEXT NOT NULL,                        -- Audit reason why statement passed admission test
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'retired'))
);

-- Raw source documents in object store
CREATE TABLE raw_document (
    id            SERIAL PRIMARY KEY,
    source        TEXT NOT NULL,                        -- 'dip' | 'bundestag_xml' | 'manifesto' | 'bpb' ...
    url           TEXT,
    object_key    TEXT NOT NULL,                        -- Path in object store
    sha256        CHAR(64) NOT NULL UNIQUE,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Individual evidence items supporting positions
CREATE TABLE evidence_item (
    id            SERIAL PRIMARY KEY,
    party_id      INT NOT NULL REFERENCES party(id),
    statement_id  INT NOT NULL REFERENCES statement(id),
    document_id   INT NOT NULL REFERENCES raw_document(id),
    tier          SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
    direction     NUMERIC(3,2) NOT NULL CHECK (direction BETWEEN -1 AND 1),
    item_weight   NUMERIC(3,2) NOT NULL DEFAULT 1.0,    -- Reduced weight for abstention, etc.
    evidence_date DATE NOT NULL,
    extract       TEXT NOT NULL,                        -- Verbatim text quote or vote details
    coder_a       TEXT NOT NULL,                        -- Coder identity
    coder_b       TEXT,                                 -- Second coder for double blind
    resolution    TEXT,                                 -- Resolution details if coders diverged
    verified      BOOLEAN NOT NULL DEFAULT FALSE
);

-- Index for speedy cell evaluations during release builds
CREATE INDEX idx_evidence_cell ON evidence_item(party_id, statement_id) WHERE verified;

-- Materialized position snapshots per release
CREATE TABLE position_snapshot (
    release_tag   TEXT NOT NULL,
    party_id      INT NOT NULL REFERENCES party(id),
    statement_id  INT NOT NULL REFERENCES statement(id),
    p             NUMERIC(4,3),                         -- NULL = keine belegbare Position
    confidence    NUMERIC(3,2),
    p_said        NUMERIC(4,3),                         -- T2-only (what they say)
    p_did         NUMERIC(4,3),                         -- T1-only (what they did)
    divergent     BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (release_tag, party_id, statement_id)
);

-- Publicly declared coalition exclusions (vetoes)
CREATE TABLE coalition_exclusion (
    id            SERIAL PRIMARY KEY,
    election_id   INT NOT NULL REFERENCES election(id),
    party_a_id    INT NOT NULL REFERENCES party(id),
    party_b_id    INT NOT NULL REFERENCES party(id),
    document_id   INT REFERENCES raw_document(id),
    reaffirmed_at DATE NOT NULL,
    CHECK (party_a_id < party_b_id)                    -- Avoid duplicate entries (A,B and B,A)
);

-- Strict, append-only log table for human coder auditing
CREATE TABLE audit_log (
    id            BIGSERIAL PRIMARY KEY,
    actor         TEXT NOT NULL,
    action        TEXT NOT NULL,
    entity        TEXT NOT NULL,
    detail        JSONB NOT NULL,
    at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent update/delete on audit log
CREATE OR REPLACE FUNCTION block_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries are immutable and cannot be updated or deleted.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_block_audit_mutation
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();
