"""Local configuration helpers."""

from dotenv import load_dotenv


# Load local secrets before modules read environment variables at import time.
load_dotenv()
