ALTER TABLE claude_usage ADD COLUMN IF NOT EXISTS tmp_check boolean;
ALTER TABLE claude_usage DROP COLUMN IF EXISTS tmp_check;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'claude_usage_pkey'
  ) THEN
    ALTER TABLE claude_usage ADD PRIMARY KEY (id, called_at);
  END IF;
END $$;

SELECT create_hypertable('claude_usage', 'called_at', if_not_exists => TRUE, migrate_data => TRUE);

CREATE TABLE IF NOT EXISTS economic_indicators (
    entity_id       UUID REFERENCES entities(id) NOT NULL,
    indicator       TEXT NOT NULL,
    value           NUMERIC NOT NULL,
    unit            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL,
    source_id       UUID REFERENCES sources(id),
    PRIMARY KEY (entity_id, indicator, recorded_at)
);
SELECT create_hypertable('economic_indicators', 'recorded_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS commodity_prices (
    commodity       TEXT NOT NULL,
    price           NUMERIC NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    unit            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL,
    source_id       UUID REFERENCES sources(id),
    PRIMARY KEY (commodity, recorded_at)
);
SELECT create_hypertable('commodity_prices', 'recorded_at', if_not_exists => TRUE);

SELECT hypertable_name FROM timescaledb_information.hypertables;
