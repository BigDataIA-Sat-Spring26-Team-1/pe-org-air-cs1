CREATE TABLE IF NOT EXISTS company_signals (
    signal_id VARCHAR(255) PRIMARY KEY,
    company_ticker VARCHAR(20) NOT NULL,
    signal_type VARCHAR(50), -- 'HIRING', 'PATENTS', 'TECH_STACK'
    raw_value FLOAT,
    normalized_score FLOAT, -- 0-100
    metadata VARIANT, -- JSON details (e.g. top keywords, patent titles)
    collection_date DATE DEFAULT CURRENT_DATE(),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS company_scores (
    score_id VARCHAR(255) PRIMARY KEY,
    company_ticker VARCHAR(20) NOT NULL,
    hiring_score FLOAT,
    innovation_score FLOAT,
    tech_score FLOAT,
    composite_score FLOAT,
    grade VARCHAR(5), -- 'A', 'B', etc.
    calculated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
