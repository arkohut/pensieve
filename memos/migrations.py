from pathlib import Path
from alembic.config import Config
from alembic import command
from .config import settings


def run_migrations():
    """Run all pending database migrations."""
    # Get the directory containing the migrations
    migrations_dir = Path(__file__).parent / "migrations"
    alembic_dir = migrations_dir / "alembic"

    # Create an Alembic configuration
    alembic_cfg = Config(str(migrations_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # Run the migration
    command.upgrade(alembic_cfg, "head")
