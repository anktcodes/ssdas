-- Run this SQL to add JSON field for additional metrics

\c ssdas

-- Add JSON column for additional metrics and chart data
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS additional_metrics JSONB;

-- Add new columns for additional metrics
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS growth_rate_week DECIMAL(10, 2);
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS growth_rate_month DECIMAL(10, 2);
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS avg_transaction_value DECIMAL(15, 2);
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS peak_day VARCHAR(20);
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS total_quantity DECIMAL(15, 2);
