"""Database initializer classes for different database backends."""

import sys
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
import sqlite_vec

from ..models import RawBase, PluginModel, LibraryModel, LibraryPluginModel


def setup_database(settings, **engine_kwargs):
    """Set up and initialize the database.
    
    Args:
        settings: Application settings containing database configuration
        **engine_kwargs: Additional keyword arguments to pass to create_engine
        
    Returns:
        tuple: (engine, initializer) where engine is the SQLAlchemy engine and
               initializer is the appropriate DatabaseInitializer instance
    """
    engine, initializer = create_db_initializer(settings, **engine_kwargs)
    initializer.init_database()
    return engine, initializer


def init_database(settings):
    """Initialize the database."""
    engine, initializer = create_db_initializer(settings)
    return initializer.init_database()


def recreate_fts_and_vec_tables(settings):
    """Recreate the database-specific tables without repopulating data."""
    engine, initializer = create_db_initializer(settings)
    return initializer.recreate_index_tables()


def initialize_default_plugins(session):
    """Initialize default plugins in the database."""
    default_plugins = [
        PluginModel(
            name="builtin_vlm", description="VLM Plugin", webhook_url="/plugins/vlm"
        ),
        PluginModel(
            name="builtin_ocr", description="OCR Plugin", webhook_url="/plugins/ocr"
        ),
    ]

    for plugin in default_plugins:
        existing_plugin = session.query(PluginModel).filter_by(name=plugin.name).first()
        if not existing_plugin:
            session.add(plugin)

    session.commit()

    return default_plugins


def init_default_libraries(session, default_plugins, settings):
    """Initialize default libraries and associate them with plugins."""
    default_libraries = [
        LibraryModel(name=settings.default_library),
    ]

    for library in default_libraries:
        existing_library = (
            session.query(LibraryModel).filter_by(name=library.name).first()
        )
        if not existing_library:
            session.add(library)

    for plugin in default_plugins:
        bind_response = session.query(PluginModel).filter_by(name=plugin.name).first()
        if bind_response:
            # Check if the LibraryPluginModel already exists
            existing_library_plugin = (
                session.query(LibraryPluginModel)
                .filter_by(library_id=1, plugin_id=bind_response.id)
                .first()
            )

            if not existing_library_plugin:
                library_plugin = LibraryPluginModel(
                    library_id=1, plugin_id=bind_response.id
                )  # Assuming library_id=1 for default libraries
                session.add(library_plugin)

    session.commit()


def create_db_initializer(settings, **engine_kwargs):
    """Create a database engine and initializer based on settings.
    
    Args:
        settings: Application settings containing database configuration
        **engine_kwargs: Additional keyword arguments to pass to create_engine
        
    Returns:
        tuple: (engine, initializer) where engine is the SQLAlchemy engine and 
               initializer is the appropriate DatabaseInitializer instance
    """
    default_engine_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 60,
        "pool_recycle": 3600,
    }
    
    if settings.is_sqlite:
        default_engine_kwargs["connect_args"] = {"timeout": 60}
    
    # Override defaults with any provided kwargs
    default_engine_kwargs.update(engine_kwargs)
    
    engine = create_engine(
        settings.database_url,
        **default_engine_kwargs
    )
        
    # Create the appropriate initializer based on database type
    if settings.is_sqlite:
        initializer = SQLiteInitializer(engine, settings)
    else:
        print("Using PostgreSQL")
        initializer = PostgreSQLInitializer(engine, settings)
    
    return engine, initializer


class DatabaseInitializer:
    """Base class for database initialization."""
    def __init__(self, engine, settings):
        self.engine = engine
        self.settings = settings

    def init_database(self) -> bool:
        """Initialize the database with common tables and data."""
        try:
            # Create all tables defined in SQLAlchemy models
            RawBase.metadata.create_all(self.engine)
            print(f"Database initialized successfully at {self.settings.database_url}")

            # Initialize database-specific features
            self.init_specific_features()

            # Initialize default data
            Session = sessionmaker(bind=self.engine)
            with Session() as session:
                default_plugins = initialize_default_plugins(session)
                init_default_libraries(session, default_plugins, self.settings)

            return True
        except OperationalError as e:
            print(f"Error initializing database: {e}")
            return False

    def init_extensions(self):
        """Initialize database extensions. To be implemented by subclasses."""
        pass

    def init_specific_features(self):
        """Initialize database-specific features. To be implemented by subclasses."""
        pass

    def recreate_index_tables(self) -> bool:
        """Recreate database-specific index tables. To be implemented by subclasses."""
        pass


class SQLiteInitializer(DatabaseInitializer):
    """SQLite-specific database initializer."""
    def __init__(self, engine, settings):
        super().__init__(engine, settings)
        self.init_extensions()

    def init_extensions(self):
        """Initialize SQLite-specific extensions."""
        event.listen(self.engine, "connect", self._load_sqlite_extensions)

    def _load_sqlite_extensions(self, dbapi_conn, connection_record):
        """Load SQLite extensions for full-text search and vector operations."""
        try:
            dbapi_conn.enable_load_extension(True)
        except AttributeError as e:
            print("Error: Current SQLite3 build doesn't support loading extensions.")
            print("\nRecommended solutions:")
            print("1. Install Python using Conda (recommended for both Windows and macOS):")
            print("   conda create -n yourenv python")
            print("   conda activate yourenv")
            print("\n2. Or on macOS, you can use Homebrew:")
            print("   brew install python")
            print(f"\nDetailed error: {str(e)}")
            raise

        # load simple tokenizer
        current_dir = Path(__file__).parent.parent.resolve()
        if sys.platform.startswith("linux"):
            lib_path = current_dir / "simple_tokenizer" / "linux" / "libsimple"
        elif sys.platform == "win32":
            lib_path = current_dir / "simple_tokenizer" / "windows" / "simple"
        elif sys.platform == "darwin":
            lib_path = current_dir / "simple_tokenizer" / "macos" / "libsimple"
        else:
            raise OSError(f"Unsupported operating system: {sys.platform}")

        dbapi_conn.load_extension(str(lib_path))
        dict_path = current_dir / "simple_tokenizer" / "dict"
        dbapi_conn.execute(f"SELECT jieba_dict('{dict_path}')")

        # load vector ext
        sqlite_vec.load(dbapi_conn)

        # Set WAL mode after loading extensions
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    def init_specific_features(self):
        """Initialize SQLite-specific features like FTS and vector extensions."""
        # Create FTS and Vec tables
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                    id, filepath, tags, metadata,
                    tokenize = 'simple 0',
                    prefix = '2 3 4'
                )
                """
                )
            )

            conn.execute(
                text(
                    f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS entities_vec_v2 USING vec0(
                    embedding float[{self.settings.embedding.num_dim}] distance_metric=cosine,
                    file_type_group text,
                    created_at_timestamp integer,
                    file_created_at_timestamp integer,
                    file_created_at_date text partition key,
                    app_name text,
                    library_id integer
                )
                """
                )
            )

    def recreate_index_tables(self) -> bool:
        """Recreate SQLite-specific index tables (FTS and vector tables)."""
        Session = sessionmaker(bind=self.engine)
        
        with Session() as session:
            try:
                # Drop existing tables
                session.execute(text("DROP TABLE IF EXISTS entities_fts"))
                session.execute(text("DROP TABLE IF EXISTS entities_vec_v2"))

                # Recreate entities_fts table
                session.execute(
                    text(
                        """
                    CREATE VIRTUAL TABLE entities_fts USING fts5(
                        id, filepath, tags, metadata,
                        tokenize = 'simple 0',
                        prefix = '2 3 4'
                    )
                    """
                    )
                )

                # Recreate entities_vec_v2 table
                session.execute(
                    text(
                        f"""
                    CREATE VIRTUAL TABLE entities_vec_v2 USING vec0(
                        embedding float[{self.settings.embedding.num_dim}] distance_metric=cosine,
                        file_type_group text,
                        created_at_timestamp integer,
                        file_created_at_timestamp integer,
                        file_created_at_date text partition key,
                        app_name text,
                        library_id integer
                    )
                    """
                    )
                )

                session.commit()
                print("Successfully recreated entities_fts and entities_vec_v2 tables.")
                return True
            except Exception as e:
                session.rollback()
                print(f"Error recreating tables: {e}")
                return False


class PostgreSQLInitializer(DatabaseInitializer):
    def __init__(self, engine, settings):
        super().__init__(engine, settings)
        self.init_extensions()

    """PostgreSQL-specific database initializer."""
    def init_extensions(self):
        """Initialize PostgreSQL-specific extensions."""
        with self.engine.connect() as conn:
            # Create extensions in a separate transaction
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    def init_specific_features(self):
        """Initialize PostgreSQL-specific features."""
        with self.engine.connect() as conn:
            # Create the tsvector column and index for full-text search
            conn.execute(
                text(
                    f"""
                    -- Create a table to store the full-text search data
                    CREATE TABLE IF NOT EXISTS entities_fts (
                        id INTEGER PRIMARY KEY,
                        filepath TEXT,
                        tags TEXT,
                        metadata TEXT,
                        search_vector tsvector GENERATED ALWAYS AS (
                            setweight(to_tsvector('simple', coalesce(filepath, '')), 'A') ||
                            setweight(to_tsvector('simple', coalesce(tags, '')), 'B') ||
                            setweight(to_tsvector('simple', coalesce(metadata, '')), 'C')
                        ) STORED,
                        -- Add raw text columns for prefix/substring search
                        search_text TEXT GENERATED ALWAYS AS (
                            coalesce(filepath, '') || ' ' || 
                            coalesce(tags, '') || ' ' || 
                            coalesce(metadata, '')
                        ) STORED
                    );

                    -- Create a GIN index for fast full-text search
                    CREATE INDEX IF NOT EXISTS idx_entities_fts_search_vector 
                    ON entities_fts USING gin(search_vector);

                    -- Create trigram index for fuzzy matching on filepath and search_text
                    CREATE INDEX IF NOT EXISTS idx_entities_fts_filepath_trgm 
                    ON entities_fts USING gin(filepath gin_trgm_ops);
                    CREATE INDEX IF NOT EXISTS idx_entities_fts_search_text_trgm
                    ON entities_fts USING gin(search_text gin_trgm_ops);
                    """
                )
            )
            conn.commit()

            # Create vector table and indexes in a separate transaction
            conn.execute(
                text(
                    f"""
                    -- Create vector search table
                    CREATE TABLE IF NOT EXISTS entities_vec_v2 (
                        rowid INTEGER PRIMARY KEY,
                        embedding vector({self.settings.embedding.num_dim}),
                        file_type_group TEXT,
                        created_at_timestamp INTEGER,
                        file_created_at_timestamp INTEGER,
                        file_created_at_date TEXT,
                        app_name TEXT,
                        library_id INTEGER
                    );

                    -- Create index for vector similarity search using HNSW
                    CREATE INDEX IF NOT EXISTS idx_entities_vec_v2_embedding 
                    ON entities_vec_v2 USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);

                    -- Create indexes for filtering
                    CREATE INDEX IF NOT EXISTS idx_entities_vec_v2_file_type_group 
                    ON entities_vec_v2(file_type_group);
                    CREATE INDEX IF NOT EXISTS idx_entities_vec_v2_file_created_at_date 
                    ON entities_vec_v2(file_created_at_date);
                    CREATE INDEX IF NOT EXISTS idx_entities_vec_v2_app_name 
                    ON entities_vec_v2(app_name);
                    CREATE INDEX IF NOT EXISTS idx_entities_vec_v2_library_id 
                    ON entities_vec_v2(library_id);
                    """
                )
            )
            conn.commit()

    def recreate_index_tables(self) -> bool:
        """Recreate PostgreSQL-specific index tables."""
        Session = sessionmaker(bind=self.engine)
        
        with Session() as session:
            try:
                # Drop existing tables
                session.execute(text("DROP TABLE IF EXISTS entities_fts CASCADE"))
                session.execute(text("DROP TABLE IF EXISTS entities_vec_v2 CASCADE"))
                session.commit()

                # Ensure extensions are created
                session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()

                # Recreate entities_fts table with tsvector support
                session.execute(
                    text(
                        f"""
                        CREATE TABLE entities_fts (
                            id INTEGER PRIMARY KEY,
                            filepath TEXT,
                            tags TEXT,
                            metadata TEXT,
                            search_vector tsvector GENERATED ALWAYS AS (
                                setweight(to_tsvector('simple', coalesce(filepath, '')), 'A') ||
                                setweight(to_tsvector('simple', coalesce(tags, '')), 'B') ||
                                setweight(to_tsvector('simple', coalesce(metadata, '')), 'C')
                            ) STORED,
                            -- Add raw text columns for prefix/substring search
                            search_text TEXT GENERATED ALWAYS AS (
                                coalesce(filepath, '') || ' ' || 
                                coalesce(tags, '') || ' ' || 
                                coalesce(metadata, '')
                            ) STORED
                        );

                        -- Create a GIN index for fast full-text search
                        CREATE INDEX idx_entities_fts_search_vector 
                        ON entities_fts USING gin(search_vector);

                        -- Create trigram index for fuzzy matching on filepath and search_text
                        CREATE INDEX idx_entities_fts_filepath_trgm 
                        ON entities_fts USING gin(filepath gin_trgm_ops);
                        CREATE INDEX idx_entities_fts_search_text_trgm
                        ON entities_fts USING gin(search_text gin_trgm_ops);
                        """
                    )
                )
                session.commit()

                # Create vector table and indexes in a separate transaction
                session.execute(
                    text(
                        f"""
                        -- Create vector search table
                        CREATE TABLE entities_vec_v2 (
                            rowid INTEGER PRIMARY KEY,
                            embedding vector({self.settings.embedding.num_dim}),
                            file_type_group TEXT,
                            created_at_timestamp INTEGER,
                            file_created_at_timestamp INTEGER,
                            file_created_at_date TEXT,
                            app_name TEXT,
                            library_id INTEGER
                        );

                        -- Create index for vector similarity search using HNSW
                        CREATE INDEX idx_entities_vec_v2_embedding 
                        ON entities_vec_v2 USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);

                        -- Create indexes for filtering
                        CREATE INDEX idx_entities_vec_v2_file_type_group 
                        ON entities_vec_v2(file_type_group);
                        CREATE INDEX idx_entities_vec_v2_file_created_at_date 
                        ON entities_vec_v2(file_created_at_date);
                        CREATE INDEX idx_entities_vec_v2_app_name 
                        ON entities_vec_v2(app_name);
                        CREATE INDEX idx_entities_vec_v2_library_id 
                        ON entities_vec_v2(library_id);
                        """
                    )
                )
                session.commit()

                print("Successfully recreated entities_fts and entities_vec_v2 tables.")
                return True
            except Exception as e:
                session.rollback()
                print(f"Error recreating tables: {e}")
                return False 