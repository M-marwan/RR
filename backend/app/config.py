import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
_ENV_FILE = _HERE.parent.parent / ".env"

load_dotenv(dotenv_path=_ENV_FILE if _ENV_FILE.exists() else ".env", override=False)


class Settings:
    def __init__(self):
        # PostgreSQL
        self.postgres_db = os.getenv("POSTGRES_DB", "rr_command_center")
        self.postgres_user = os.getenv("POSTGRES_USER", "rr_admin")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "rr_secret_change_me")
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://rr_admin:rr_secret_change_me@localhost:5433/rr_command_center",
        )

        # Redis
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")

        # Claude CLI
        self.claude_cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        self.claude_max_concurrent_calls = int(os.getenv("CLAUDE_MAX_CONCURRENT_CALLS", "2"))
        self.claude_rate_limit_delay_seconds = int(
            os.getenv("CLAUDE_RATE_LIMIT_DELAY_SECONDS", "5")
        )

        # Microsoft Entra (Azure AD) — leave both empty in dev to disable auth.
        # When set, every /api/* request must carry a valid Bearer JWT issued
        # for `ms_client_id` by tenant `ms_tenant_id`.
        self.ms_tenant_id = os.getenv("MS_TENANT_ID", "")
        self.ms_client_id = os.getenv("MS_CLIENT_ID", "")
        # Comma-separated list of upn / email values allowed to skip auth
        # entirely (use only for the principal's local dev). Empty = no bypass.
        self.ms_dev_bypass_emails = [
            e.strip().lower()
            for e in os.getenv("MS_DEV_BYPASS_EMAILS", "").split(",")
            if e.strip()
        ]

        # Gmail — primary
        self.gmail_marwan_client_id = os.getenv("GMAIL_MARWAN_CLIENT_ID", "")
        self.gmail_marwan_client_secret = os.getenv("GMAIL_MARWAN_CLIENT_SECRET", "")
        self.gmail_marwan_token_path = os.getenv(
            "GMAIL_MARWAN_TOKEN_PATH", "data/credentials/gmail_marwan.json"
        )
        self.gmail_marwan_address = os.getenv(
            "GMAIL_MARWAN_ADDRESS", "014.marwan@gmail.com"
        )

        # Gmail — subscriptions
        self.gmail_subscriptions_token_path = os.getenv(
            "GMAIL_SUBSCRIPTIONS_TOKEN_PATH", "data/credentials/gmail_subscriptions.json"
        )
        self.gmail_subscriptions_address = os.getenv(
            "GMAIL_SUBSCRIPTIONS_ADDRESS", "rr.subscriptions@gmail.com"
        )

        # Twitter / X
        self.twitter_bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")
        self.twitter_api_key = os.getenv("TWITTER_API_KEY", "")
        self.twitter_api_secret = os.getenv("TWITTER_API_SECRET", "")

        # Brave Search
        self.brave_search_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.brave_search_daily_quota = int(os.getenv("BRAVE_SEARCH_DAILY_QUOTA", "65"))

        # Paid portals
        self.kpler_username = os.getenv("KPLER_USERNAME", "")
        self.kpler_password = os.getenv("KPLER_PASSWORD", "")
        self.platts_username = os.getenv("PLATTS_USERNAME", "")
        self.platts_password = os.getenv("PLATTS_PASSWORD", "")
        self.bloomberg_username = os.getenv("BLOOMBERG_USERNAME", "")
        self.bloomberg_password = os.getenv("BLOOMBERG_PASSWORD", "")
        self.sp_global_username = os.getenv("SP_GLOBAL_USERNAME", "")
        self.sp_global_password = os.getenv("SP_GLOBAL_PASSWORD", "")

        # Timezone
        self.tz = os.getenv("TZ", "Asia/Dubai")

        # RR source path
        self.rr_source_path = os.getenv(
            "RR_SOURCE_PATH",
            "C:/Users/HELIOS/OneDrive - giavc.com/Desktop/Claude/.claude/RR/RR",
        )

        # Frontend
        self.next_public_api_url = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8001")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
