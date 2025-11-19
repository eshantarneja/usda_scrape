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
USDA_REPORTS_PAGE = f"{USDA_BASE_URL}/market-news/weekly-and-monthly-beef-reports"

# Report configurations
REPORTS_CONFIG = {
    "branded_beef": {
        "name": "Boxed Beef Cuts-Branded Product-Negotiated Sales",
        "schedule": "Monday",
        "report_type": "branded_beef"
    },
    "ungraded_beef": {
        "name": "Boxed Beef Cuts-Ungraded Product",
        "schedule": "Monday",
        "report_type": "ungraded_beef"
    }
}

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
