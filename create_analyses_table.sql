-- Run this SQL in PostgreSQL to create the analyses table

-- Connect to your database first
\c ssdas

-- Create analyses table to store analysis results
CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Detected columns
    date_column VARCHAR(100),
    item_column VARCHAR(100),
    qty_column VARCHAR(100),
    rate_column VARCHAR(100),
    amount_column VARCHAR(100),
    
    -- Analysis results
    total_sales DECIMAL(15, 2),
    last_7_days_sales DECIMAL(15, 2),
    last_30_days_sales DECIMAL(15, 2),
    avg_sales_per_day_week DECIMAL(15, 2),
    avg_sales_per_day_month DECIMAL(15, 2),
    
    -- Metadata
    total_records INTEGER,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on user_id for faster queries
CREATE INDEX idx_analyses_user_id ON analyses(user_id);
CREATE INDEX idx_analyses_uploaded_at ON analyses(uploaded_at DESC);
