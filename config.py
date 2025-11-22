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
    }
}

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
