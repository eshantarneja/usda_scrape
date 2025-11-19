# Quick Reference

## Common Commands

### Setup
```bash
# Initial setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### Running the Scraper

```bash
# Run both reports
python main.py

# Run specific report
python main.py --reports branded_beef
python main.py --reports ungraded_beef

# Force re-processing
python main.py --force

# Verbose mode
python main.py --verbose

# Multiple reports with force
python main.py --reports branded_beef ungraded_beef --force --verbose
```

### Testing Components

```bash
# Test database connection
python database.py

# Test scraper (shows available reports)
python scraper.py

# Test PDF parser (requires PDF file)
python pdf_parser.py path/to/report.pdf
```

## File Structure Quick Reference

```
usda_scrape/
├── config.py              - Configuration (URLs, report types)
├── scraper.py             - Fetches PDFs from USDA website
├── pdf_parser.py          - Parses PDF tables
├── database.py            - Supabase database operations
├── main.py                - Main orchestration script
├── schema.sql             - Database schema
├── requirements.txt       - Python dependencies
├── .env                   - Environment variables (create from .env.example)
└── .github/workflows/     - GitHub Actions schedules
```

## Database Tables

### reports
- Tracks each scraped report
- Key fields: `report_type`, `report_date`, `pdf_url`, `status`

### products
- Master list of products
- Key fields: `product_name`, `report_type`

### prices
- Time-series pricing data
- Key fields: `product_id`, `report_date`, `price`, `volume`

## Useful SQL Queries

### Latest prices for all products
```sql
SELECT
  p.product_name,
  pr.price,
  pr.low_price,
  pr.high_price,
  pr.volume,
  pr.report_date
FROM prices pr
JOIN products p ON pr.product_id = p.id
ORDER BY pr.report_date DESC, p.product_name
LIMIT 100;
```

### Price history for specific product
```sql
SELECT
  pr.report_date,
  pr.price,
  pr.low_price,
  pr.high_price,
  pr.volume
FROM prices pr
JOIN products p ON pr.product_id = p.id
WHERE p.product_name ILIKE '%beef%'  -- Change search term
ORDER BY pr.report_date DESC;
```

### Check scraping status
```sql
SELECT
  report_type,
  report_date,
  status,
  scraped_at,
  error_message
FROM reports
ORDER BY scraped_at DESC
LIMIT 20;
```

### Products by report type
```sql
SELECT
  report_type,
  COUNT(*) as product_count
FROM products
GROUP BY report_type;
```

### Price records per day
```sql
SELECT
  report_date,
  COUNT(*) as price_count
FROM prices
GROUP BY report_date
ORDER BY report_date DESC;
```

## GitHub Actions

### Manual Trigger
1. Go to repository on GitHub
2. Click "Actions" tab
3. Select workflow
4. Click "Run workflow"
5. Select branch and options
6. Click green "Run workflow" button

### View Logs
1. Actions tab
2. Click on workflow run
3. Click on job name
4. Expand steps to see output

### Workflow Schedules
- **Branded Beef**: Mondays 2 PM UTC (`scrape-branded-beef.yml`)
- **Ungraded Beef**: Fridays 2 PM UTC (`scrape-ungraded-beef.yml`)
- **All Reports**: Manual only (`scrape-all-reports.yml`)

## Environment Variables

Required in `.env` file:
```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Required GitHub Secrets:
- `SUPABASE_URL`
- `SUPABASE_KEY`

## Report Types

Currently configured:

| Report Type | USDA Report Name | Schedule |
|-------------|------------------|----------|
| `branded_beef` | Boxed Beef Cuts-Branded Product-Negotiated Sales | Monday |
| `ungraded_beef` | Boxed Beef Cuts-Ungraded Product – Negotiated Sales | Friday |

## Troubleshooting

### "No module named 'requests'"
```bash
pip install -r requirements.txt
```

### "SUPABASE_URL and SUPABASE_KEY must be set"
- Check `.env` file exists
- Verify credentials are correct
- No extra spaces or quotes in `.env`

### "No reports found"
- USDA website may be down temporarily
- Report names may have changed - check `config.py`

### GitHub Actions fails
- Verify GitHub Secrets are set
- Check workflow logs for specific error
- Ensure repository has Actions enabled

### PDF parsing returns no data
- PDF structure may have changed
- Check actual PDF to verify it has tables
- May need to adjust `pdf_parser.py` column detection

## Useful Links

- [USDA Reports Page](https://www.ams.usda.gov/market-news/weekly-and-monthly-beef-reports)
- [Supabase Dashboard](https://supabase.com/dashboard)
- [Crontab.guru](https://crontab.guru) - Cron schedule helper
- [GitHub Actions Docs](https://docs.github.com/en/actions)

## Quick Tips

1. **Always use virtual environment** to avoid dependency conflicts
2. **Test locally first** before relying on GitHub Actions
3. **Check Supabase logs** in dashboard for database errors
4. **Use `--verbose` flag** when debugging
5. **Start with manual workflow** to test GitHub Actions setup
6. **Monitor first few runs** to ensure data quality
7. **Set up GitHub notifications** for workflow failures

## Adding New Reports

1. Find report on USDA website
2. Add to `REPORTS_CONFIG` in `config.py`:
   ```python
   "new_report": {
       "name": "Exact Name from Website",
       "schedule": "Monday",
       "report_type": "new_report"
   }
   ```
3. Create new workflow in `.github/workflows/`
4. Test: `python main.py --reports new_report --verbose`

## Data Export

### CSV Export from Supabase
1. Go to Table Editor
2. Select table
3. Click "..." menu
4. Choose "Download as CSV"

### API Access
```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
response = supabase.table('prices').select('*').execute()
data = response.data
```

## Performance Notes

- Average processing time: 2-5 minutes per report
- PDF download: ~10-30 seconds
- PDF parsing: ~1-2 minutes
- Database insertion: ~1-2 minutes
- Total: ~5 minutes for both reports
