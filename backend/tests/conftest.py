"""Test configuration.

Sets safe defaults before Settings is first constructed so the app can be
imported without real IDP/DB/S3 credentials.
"""

import os

os.environ.setdefault("AUTH_DEV_FALLBACK", "true")
os.environ.setdefault("APPLICATION_ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
