BEGIN;

CREATE TABLE schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL
);

CREATE TABLE datasets (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    description text,
    created_at timestamptz NOT NULL
);

CREATE TABLE dataset_versions (
    id uuid PRIMARY KEY,
    dataset_id uuid NOT NULL REFERENCES datasets(id),
    version text NOT NULL,
    content_hash text NOT NULL UNIQUE,
    source text NOT NULL,
    timeframe text NOT NULL,
    timezone text NOT NULL,
    currency text NOT NULL,
    price_unit text NOT NULL,
    price_adjustment text NOT NULL,
    volume_adjustment text NOT NULL,
    corporate_action_policy text NOT NULL,
    raw_artifact_uri text,
    extracted_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (dataset_id, version)
);

CREATE TABLE market_bars (
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    symbol text NOT NULL,
    trading_date date NOT NULL,
    open numeric(24,6),
    high numeric(24,6),
    low numeric(24,6),
    close numeric(24,6) NOT NULL CHECK (close > 0),
    volume numeric(30,6) CHECK (volume >= 0),
    PRIMARY KEY (dataset_version_id, symbol, trading_date)
);

CREATE TABLE backtest_runs (
    id uuid PRIMARY KEY,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    strategy_id text NOT NULL,
    engine_version text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    initial_cash numeric(24,6) NOT NULL CHECK (initial_cash > 0),
    config jsonb NOT NULL,
    strategy_parameters jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','running','succeeded','failed','cancelled')),
    error_code text,
    error_detail jsonb,
    created_at timestamptz NOT NULL,
    started_at timestamptz,
    completed_at timestamptz
);

CREATE TABLE signals (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    sequence_no bigint NOT NULL,
    signal_time date NOT NULL,
    side text NOT NULL CHECK (side IN ('BUY','SELL')),
    reason text NOT NULL,
    pivot numeric(24,6),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, sequence_no)
);

CREATE TABLE orders (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    signal_id uuid NOT NULL UNIQUE REFERENCES signals(id),
    created_time date NOT NULL,
    side text NOT NULL CHECK (side IN ('BUY','SELL')),
    status text NOT NULL CHECK (status IN ('pending','filled','rejected','unfilled')),
    quantity bigint CHECK (quantity > 0),
    rejection_reason text,
    sizing_details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE fills (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    order_id uuid NOT NULL UNIQUE REFERENCES orders(id),
    fill_time date NOT NULL,
    side text NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity bigint NOT NULL CHECK (quantity > 0),
    fill_price numeric(24,6) NOT NULL CHECK (fill_price > 0),
    fee numeric(24,6) NOT NULL CHECK (fee >= 0)
);

CREATE TABLE trades (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    entry_fill_id uuid NOT NULL UNIQUE REFERENCES fills(id),
    exit_fill_id uuid NOT NULL UNIQUE REFERENCES fills(id),
    quantity bigint NOT NULL CHECK (quantity > 0),
    entry_value numeric(24,6) NOT NULL,
    exit_value numeric(24,6) NOT NULL,
    total_fees numeric(24,6) NOT NULL,
    net_realized_pnl numeric(24,6) NOT NULL,
    close_reason text NOT NULL
);

CREATE TABLE equity_snapshots (
    run_id uuid NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    trading_date date NOT NULL,
    cash numeric(24,6) NOT NULL,
    quantity bigint NOT NULL CHECK (quantity >= 0),
    market_value numeric(24,6) NOT NULL,
    equity numeric(24,6) NOT NULL,
    unrealized_pnl numeric(24,6) NOT NULL,
    PRIMARY KEY (run_id, trading_date)
);

CREATE TABLE open_positions (
    run_id uuid PRIMARY KEY REFERENCES backtest_runs(id) ON DELETE CASCADE,
    entry_fill_id uuid NOT NULL UNIQUE REFERENCES fills(id),
    quantity bigint NOT NULL CHECK (quantity > 0),
    entry_pivot numeric(24,6) NOT NULL,
    stop_reference numeric(24,6) NOT NULL,
    market_value numeric(24,6) NOT NULL,
    unrealized_pnl numeric(24,6) NOT NULL
);

CREATE INDEX backtest_runs_status_created_idx ON backtest_runs (status, created_at DESC);
CREATE INDEX backtest_runs_dataset_strategy_created_idx ON backtest_runs (dataset_version_id, strategy_id, created_at DESC);
CREATE INDEX signals_run_time_idx ON signals (run_id, signal_time);
CREATE INDEX orders_run_status_idx ON orders (run_id, status);
CREATE INDEX fills_run_time_idx ON fills (run_id, fill_time);
CREATE INDEX trades_run_idx ON trades (run_id);

INSERT INTO schema_migrations (version, applied_at) VALUES ('001_initial.sql', now());

COMMIT;
