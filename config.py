"""Configuration settings for USDA scraper."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# USDA configuration
USDA_BASE_URL = "https://www.ams.usda.gov"

# Report configurations with direct PDF URLs
REPORTS_CONFIG = {
    "branded_beef": {
        "name": "Boxed Beef Cuts-Branded Product-Negotiated Sales",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/AMS_2457.pdf",
        "schedule": "weekly",  # Mondays
        "report_type": "branded_beef"
    },
    "ungraded_beef": {
        "name": "Boxed Beef Cuts-Ungraded Product",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/AMS_2464.pdf",
        "schedule": "weekly",  # Mondays
        "report_type": "ungraded_beef"
    },
    "daily_afternoon": {
        "name": "National Daily Boxed Beef Cutout And Boxed Beef Cuts - Afternoon",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_2453.pdf",
        "schedule": "daily",  # Monday-Friday
        "report_type": "daily_afternoon"
    },
    "cow_beef": {
        "name": "National Weekly Cutter Cow Cutout And Boxed Cow Beef Cuts",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_2463.pdf",  # 2463 = LM_XB461; 2461 is the steer/heifer weekly
        "schedule": "weekly",  # Fridays
        "report_type": "cow_beef"
    },
    "prime_beef": {
        "name": "National Weekly Boxed Beef Cuts For Prime Product - Negotiated Sales",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_2460.pdf",  # 2460 = LM_XB456 (verified 2026-10-08)
        "schedule": "weekly",  # Mondays
        "report_type": "prime_beef",
        # Demo only: prime_report.py fetches it from the USDA datamart and sends it to
        # Demo's door. It is never written to this scraper's own database.
        "demo_only": True,
    },
    "pork_cuts": {
        "name": "National Daily Pork Report FOB Omaha",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_2498.pdf",
        "schedule": "daily",  # Monday-Friday
        "report_type": "pork_cuts"
    },
    # Poultry (added 2026-11-02 for the Demo poultry catalog). Both are Friday reports in
    # cents per lb: whole birds by weight class and the parts structure. The daily
    # At-a-Glance (AJ_PY010) was discontinued 2025-03-25, so these are the anchors.
    # Past weeks are on ESMIS (poultry_backfill.py); the mnreports PDF is the latest only.
    "weekly_chicken": {
        "name": "Weekly National Chicken Report",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_3646.pdf",  # 3646 = Weekly National Chicken (verified 2026-11-02)
        "schedule": "weekly",  # Fridays
        "report_type": "weekly_chicken",
        "esmis_slug": "weekly-national-chicken-report",
    },
    "weekly_turkey": {
        "name": "Weekly National Turkey Report",
        "pdf_url": f"{USDA_BASE_URL}/mnreports/ams_3647.pdf",  # 3647 = Weekly National Turkey (verified 2026-11-02)
        "schedule": "weekly",  # Fridays
        "report_type": "weekly_turkey",
        "esmis_slug": "weekly-national-turkey-report",
    },
}

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
