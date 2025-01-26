from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sqlite_vec
from sqlalchemy import event
from urllib.parse import urlparse

from memos import models
from memos import config as memosConfig

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = models.RawBase.metadata

# overwrite the desired value
config.set_main_option("sqlalchemy.url", memosConfig.settings.database_url)

def get_db_type():
    """Get database type from URL."""
    url = config.get_main_option("sqlalchemy.url")
    return urlparse(url).scheme

def configure_sqlite(engine):
    """Configure SQLite specific settings."""
    def load_extension(dbapi_conn, connection_record):
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
    
    event.listen(engine, 'connect', load_extension)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Configure the database connection based on the database type
    db_type = get_db_type()
    
    # Set appropriate connection parameters based on database type
    if db_type == 'postgresql':
        engine_config = {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 3600,
        }
    else:  # sqlite
        engine_config = {
            'connect_args': {'timeout': 60},
            'poolclass': pool.NullPool,  # SQLite doesn't need connection pooling
        }
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        **engine_config
    )

    # Configure SQLite extensions if needed
    if db_type == 'sqlite':
        configure_sqlite(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Add PostgreSQL-specific options
            compare_type=True,  # Compare column types
            compare_server_default=True,  # Compare default values
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
