# USDA Meat Product Price Scraper

Automated pipeline to scrape, parse, and store USDA meat product pricing data from weekly PDF reports into a Supabase database.

## Overview

This system automatically:
1. Fetches the latest USDA meat product reports from the USDA AMS website
2. Downloads PDF reports for branded and ungraded boxed beef products
3. Parses the PDFs to extract pricing data
4. Stores the data in a Supabase PostgreSQL database
5. Runs on a schedule via GitHub Actions (Mondays for branded beef, Fridays for ungraded beef)

## Features

- **Automated Scraping**: Scheduled GitHub Actions workflows for hands-free operation
- **PDF Parsing**: Robust table extraction from USDA PDF reports using pdfplumber
- **Database Integration**: Seamless integration with Supabase for cloud data storage
- **Idempotency**: Prevents duplicate data by checking for existing reports
- **Error Handling**: Comprehensive logging and error recovery
- **Extensible**: Easy to add more report types

## Project Structure

```
usda_scrape/
├── .github/
│   └── workflows/
│       ├── scrape-branded-beef.yml    # Monday schedule
│       ├── scrape-ungraded-beef.yml   # Friday schedule
│       └── scrape-all-reports.yml     # Manual trigger
├── config.py                          # Configuration settings
├── scraper.py                         # PDF scraper module
├── pdf_parser.py                      # PDF parsing logic
├── database.py                        # Supabase integration
├── main.py                            # Main orchestration script
├── schema.sql                         # Database schema
├── requirements.txt                   # Python dependencies
├── .env.example                       # Example environment variables
└── README.md                          # This file
```

## Database Schema

### Tables

1. **reports**: Tracks metadata for scraped reports
   - `id` (UUID): Primary key
   - `report_type` (VARCHAR): Type of report (e.g., 'branded_beef')
   - `report_date` (DATE): Date of the report
   - `pdf_url` (TEXT): URL of the source PDF
   - `status` (VARCHAR): Processing status ('pending', 'processing', 'completed', 'failed')
   - `scraped_at` (TIMESTAMP): When the report was scraped

2. **products**: Master list of meat products
   - `id` (UUID): Primary key
   - `product_name` (TEXT): Name of the product
   - `product_code` (VARCHAR): Optional product code
   - `category` (VARCHAR): Product category
   - `report_type` (VARCHAR): Which report type this product appears in

3. **prices**: Time-series pricing data
   - `id` (UUID): Primary key
   - `product_id` (UUID): Foreign key to products
   - `report_id` (UUID): Foreign key to reports
   - `report_date` (DATE): Date of the price
   - `price` (DECIMAL): Weighted average price
   - `low_price` (DECIMAL): Low range price
   - `high_price` (DECIMAL): High range price
   - `volume` (INTEGER): Trading volume
   - `additional_data` (JSONB): Extra metadata

## Setup Instructions

### 1. Prerequisites

- Python 3.11 or higher
- Supabase account and project
- GitHub account (for scheduled runs)

### 2. Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Navigate to the SQL Editor in your Supabase dashboard
3. Run the schema from `schema.sql` to create the tables
4. Get your project URL and API key from Settings > API

### 3. Local Development Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd usda_scrape

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your Supabase credentials
```

### 4. Configure Environment Variables

Edit `.env`:

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

### 5. GitHub Actions Setup

1. Go to your GitHub repository settings
2. Navigate to Secrets and Variables > Actions
3. Add the following repository secrets:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase API key

## Usage

### Local Execution

```bash
# Run for both report types
python main.py

# Run for specific report type
python main.py --reports branded_beef

# Force processing even if report exists
python main.py --force

# Verbose logging
python main.py --verbose
```

### Scheduled Execution (GitHub Actions)

The workflows are configured to run automatically:

- **Branded Beef**: Every Monday at 2 PM UTC
- **Ungraded Beef**: Every Friday at 2 PM UTC

You can also manually trigger workflows:

1. Go to the "Actions" tab in your GitHub repository
2. Select the workflow you want to run
3. Click "Run workflow"

### Testing Individual Components

```bash
# Test the scraper
python scraper.py

# Test the PDF parser (requires a PDF file)
python pdf_parser.py path/to/report.pdf

# Test database connection
python database.py
```

## Report Types

Currently configured report types:

1. **branded_beef**: Boxed Beef Cuts - Branded Product - Negotiated Sales
   - Published: Mondays
   - Contains pricing for branded beef products

2. **ungraded_beef**: Boxed Beef Cuts - Ungraded Product – Negotiated Sales
   - Published: Varies (configured for Fridays)
   - Contains pricing for ungraded beef products

## Adding More Reports

To add additional report types:

1. Add configuration to `config.py`:
   ```python
   REPORTS_CONFIG = {
       "new_report": {
           "name": "Report Name from USDA Website",
           "schedule": "Monday",
           "report_type": "new_report"
       }
   }
   ```

2. Create a new GitHub Actions workflow or modify existing ones

3. Run the pipeline:
   ```bash
   python main.py --reports new_report
   ```

## Monitoring and Logs

- GitHub Actions provides execution logs for each run
- Logs include detailed information about:
  - Reports found and processed
  - Number of pricing records extracted
  - Database operations
  - Any errors encountered

## Troubleshooting

### Common Issues

1. **No reports found**
   - Check if the USDA website structure has changed
   - Verify the report names in `config.py` match the website

2. **PDF parsing errors**
   - The PDF structure may have changed
   - Check `pdf_parser.py` and adjust column detection logic

3. **Database connection errors**
   - Verify Supabase credentials in environment variables
   - Check if Supabase project is active

4. **GitHub Actions failures**
   - Check repository secrets are set correctly
   - Review workflow logs for specific errors

### Debug Mode

Run with verbose logging to see detailed output:

```bash
python main.py --verbose
```

## Data Access

Query your data from Supabase:

```sql
-- Get latest prices for all products
SELECT p.product_name, pr.price, pr.report_date
FROM prices pr
JOIN products p ON pr.product_id = p.id
ORDER BY pr.report_date DESC;

-- Get price history for a specific product
SELECT pr.report_date, pr.price, pr.low_price, pr.high_price
FROM prices pr
JOIN products p ON pr.product_id = p.id
WHERE p.product_name = 'Product Name'
ORDER BY pr.report_date DESC;
```

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License

## Support

For issues or questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review GitHub Actions logs for automated runs

## Acknowledgments

- Data source: [USDA Agricultural Marketing Service](https://www.ams.usda.gov/)
- Built with: Python, pdfplumber, Supabase, GitHub Actions
