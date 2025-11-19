-- USDA Meat Product Price Scraper Database Schema
-- Run this in your Supabase SQL editor to set up the database

-- Table to track report metadata
CREATE TABLE IF NOT EXISTS usda_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    report_type VARCHAR(100) NOT NULL,
    report_date DATE NOT NULL,
    pdf_url TEXT NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(report_type, report_date)
);

-- Table to store master list of products
CREATE TABLE IF NOT EXISTS usda_products (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_code VARCHAR(100),
    category VARCHAR(100),
    report_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_name, report_type)
);

-- Table to store time-series pricing data
CREATE TABLE IF NOT EXISTS usda_prices (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES usda_products(id) ON DELETE CASCADE,
    report_id UUID NOT NULL REFERENCES usda_reports(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    volume INTEGER,
    unit VARCHAR(50),
    additional_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, report_date)
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_usda_reports_date ON usda_reports(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_usda_reports_type ON usda_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_usda_reports_status ON usda_reports(status);

CREATE INDEX IF NOT EXISTS idx_usda_products_type ON usda_products(report_type);
CREATE INDEX IF NOT EXISTS idx_usda_products_name ON usda_products(product_name);

CREATE INDEX IF NOT EXISTS idx_usda_prices_date ON usda_prices(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_usda_prices_product ON usda_prices(product_id);
CREATE INDEX IF NOT EXISTS idx_usda_prices_report ON usda_prices(report_id);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_usda_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update updated_at
CREATE TRIGGER update_usda_reports_updated_at
    BEFORE UPDATE ON usda_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_usda_updated_at_column();

CREATE TRIGGER update_usda_products_updated_at
    BEFORE UPDATE ON usda_products
    FOR EACH ROW
    EXECUTE FUNCTION update_usda_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE usda_reports IS 'Tracks metadata for scraped USDA reports';
COMMENT ON TABLE usda_products IS 'Master list of meat products across different report types';
COMMENT ON TABLE usda_prices IS 'Time-series pricing data for products';
