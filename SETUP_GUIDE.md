# Quick Setup Guide

Follow these steps to get the USDA scraper up and running.

## Step 1: Set Up Supabase (5 minutes)

1. **Create a Supabase account**
   - Go to [supabase.com](https://supabase.com)
   - Sign up or log in

2. **Create a new project**
   - Click "New Project"
   - Choose an organization
   - Enter project name (e.g., "usda-scraper")
   - Set a strong database password (save this!)
   - Select a region close to you
   - Click "Create new project"
   - Wait 2-3 minutes for project to initialize

3. **Run the database schema**
   - In your Supabase dashboard, go to the SQL Editor (left sidebar)
   - Click "New query"
   - Copy the entire contents of `schema.sql` from this repository
   - Paste into the SQL editor
   - Click "Run" or press Cmd/Ctrl + Enter
   - You should see "Success. No rows returned"

4. **Get your credentials**
   - Go to Settings (gear icon) > API
   - Copy the "Project URL" (looks like `https://xxxxx.supabase.co`)
   - Copy the "anon public" API key (starts with `eyJ...`)
   - Save these for the next step

## Step 2: Local Development Setup (5 minutes)

1. **Clone and navigate to the repository**
   ```bash
   cd usda_scrape
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv

   # Activate it
   # On macOS/Linux:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env with your favorite editor
   # Replace the placeholder values with your Supabase credentials
   ```

   Your `.env` should look like:
   ```env
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

## Step 3: Test the Setup (2 minutes)

1. **Test database connection**
   ```bash
   python database.py
   ```

   You should see: `Database manager initialized successfully`

2. **Test the scraper (dry run)**
   ```bash
   python scraper.py
   ```

   This will show you the latest reports available on the USDA website.

3. **Run the full pipeline**
   ```bash
   python main.py --verbose
   ```

   This will:
   - Fetch the latest reports
   - Download PDFs
   - Parse pricing data
   - Store in your Supabase database

   Watch the console output to see progress!

## Step 4: Set Up GitHub Actions (5 minutes)

This enables automatic scheduled scraping.

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Initial setup of USDA scraper"
   git push origin main
   ```

2. **Add GitHub Secrets**
   - Go to your GitHub repository
   - Click Settings > Secrets and variables > Actions
   - Click "New repository secret"
   - Add two secrets:

     **Secret 1:**
     - Name: `SUPABASE_URL`
     - Value: Your Supabase project URL

     **Secret 2:**
     - Name: `SUPABASE_KEY`
     - Value: Your Supabase anon key

3. **Enable GitHub Actions**
   - Go to the "Actions" tab in your repository
   - If prompted, click "I understand my workflows, go ahead and enable them"

4. **Test a workflow manually**
   - Click on "Scrape All Reports (Manual)"
   - Click "Run workflow"
   - Select the branch (usually `main`)
   - Click the green "Run workflow" button
   - Watch it execute!

## Step 5: Verify Data in Supabase (2 minutes)

1. **View your data**
   - Go to your Supabase dashboard
   - Click "Table Editor" in the left sidebar
   - You should see three tables: `reports`, `products`, `prices`
   - Click on each to see the data that was imported

2. **Run a test query**
   - Go to SQL Editor
   - Run this query to see your latest prices:
   ```sql
   SELECT
     p.product_name,
     pr.price,
     pr.report_date
   FROM prices pr
   JOIN products p ON pr.product_id = p.id
   ORDER BY pr.report_date DESC
   LIMIT 10;
   ```

## Ongoing Usage

### Scheduled Runs

Once set up, the system runs automatically:
- **Every Monday at 2 PM UTC**: Scrapes branded beef reports
- **Every Friday at 2 PM UTC**: Scrapes ungraded beef reports

No manual intervention needed!

### Manual Runs

Run locally anytime:
```bash
# Both reports
python main.py

# Just one report type
python main.py --reports branded_beef

# Force re-processing
python main.py --force
```

Or trigger via GitHub Actions:
1. Go to Actions tab
2. Select a workflow
3. Click "Run workflow"

## Customization

### Adjusting Schedules

Edit the cron expressions in `.github/workflows/*.yml`:

```yaml
schedule:
  - cron: '0 14 * * 1'  # Min Hour Day Month DayOfWeek
```

Common schedules:
- `0 14 * * 1` - Every Monday at 2 PM UTC
- `0 14 * * 5` - Every Friday at 2 PM UTC
- `0 12 * * *` - Every day at 12 PM UTC
- `0 0 * * 0` - Every Sunday at midnight UTC

Use [crontab.guru](https://crontab.guru) to help build cron expressions.

### Adding More Reports

1. Find the report on the [USDA website](https://www.ams.usda.gov/market-news/weekly-and-monthly-beef-reports)
2. Add to `config.py`:
   ```python
   "report_key": {
       "name": "Exact Report Name from Website",
       "schedule": "Monday",
       "report_type": "report_key"
   }
   ```
3. Create a new workflow file in `.github/workflows/`
4. Run it!

## Getting Help

### Check Logs

**Local runs**: Output appears in your terminal

**GitHub Actions**:
1. Go to Actions tab
2. Click on a workflow run
3. Click on the job
4. Expand steps to see detailed logs

### Common First-Time Issues

1. **"SUPABASE_URL and SUPABASE_KEY must be set"**
   - Make sure `.env` file exists and has correct values
   - Verify no extra spaces in the `.env` file

2. **"No reports found"**
   - The website might be temporarily down
   - Try again in a few minutes

3. **PDF parsing returns no data**
   - The PDF structure might be different than expected
   - Open an issue with the PDF URL for investigation

4. **GitHub Actions fails**
   - Verify secrets are set correctly in repository settings
   - Check that you used the exact names: `SUPABASE_URL` and `SUPABASE_KEY`

## Next Steps

Once everything is working:

1. **Set up monitoring**: Use GitHub's notification settings to get alerts on workflow failures
2. **Build visualizations**: Connect Supabase to tools like Retool, Metabase, or build a custom dashboard
3. **Export data**: Use Supabase's API or SQL exports to integrate with other systems
4. **Add more reports**: Expand to other USDA meat products or commodity reports

## Support

- Check the main [README.md](README.md) for detailed documentation
- Review [USDA website](https://www.ams.usda.gov/market-news/weekly-and-monthly-beef-reports) for report updates
- Open GitHub issues for bugs or feature requests

Enjoy your automated USDA data pipeline!
