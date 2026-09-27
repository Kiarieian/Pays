import os

# Set test environment variables BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "XIkBuofwH6Jk55CTrQ6ZeJwGmCWjRclh5stFnS0QQuU=")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")
