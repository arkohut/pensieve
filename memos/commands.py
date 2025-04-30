# Standard library imports
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

# Third-party imports
import httpx
import typer

# Local imports
from .config import settings, display_config

import sys
import subprocess
import platform

from .cmds.plugin import plugin_app
from .cmds.library import lib_app

import psutil
import signal
from tabulate import tabulate

try:
    from memos import __version__
except ImportError:
    __version__ = "Unknown"

BASE_URL = settings.server_endpoint

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set the logging level to WARNING or higher
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Optionally, you can set the logging level for specific libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("typer").setLevel(logging.ERROR)


def check_server_health():
    """Check if the server is running and healthy."""
    try:
        response = httpx.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200
    except httpx.RequestException:
        return False


def callback(ctx: typer.Context):
    """Callback to check server health before running any command."""
    # List of commands that require the server to be running
    server_dependent_commands = [
        "scan",
        "reindex",
        "ls",
        "create",
        "add-folder",
        "show",
        "sync",
        "bind",
        "unbind",
    ]

    if ctx.invoked_subcommand in server_dependent_commands:
        if not check_server_health():
            typer.echo("Error: Server is not running. Please start the server first.")
            raise typer.Exit(code=1)


app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

app.add_typer(plugin_app, name="plugin")
app.add_typer(lib_app, name="lib", callback=callback)


@app.command()
def serve():
    """Run the server after initializing if necessary."""
    from .service_manager import register_service_signals, remove_pid_file
    
    # 注册信号处理
    register_service_signals("serve")
    
    try:
        from .databases.initializers import init_database
        from .migrations import run_migrations
        
        db_success = init_database(settings)
        if db_success:
            run_migrations()
            
            from .server import run_server
            run_server()
        else:
            print("Server initialization failed. Unable to start the server.")
    finally:
        # 确保清理PID文件
        remove_pid_file("serve")


@app.command()
def init():
    """Initialize the database."""
    from .databases.initializers import init_database
    from .migrations import run_migrations

    db_success = init_database(settings)
    if db_success:
        run_migrations()
        print("Initialization completed successfully.")
    else:
        print("Initialization failed. Please check the error messages above.")


def get_or_create_default_library():
    """
    Get the default library or create it if it doesn't exist.
    Ensure the library has at least one folder.
    """
    from .cmds.plugin import bind

    response = httpx.get(f"{BASE_URL}/api/libraries")
    if response.status_code != 200:
        print(f"Failed to retrieve libraries: {response.status_code} - {response.text}")
        return None

    libraries = response.json()
    default_library = next(
        (lib for lib in libraries if lib["name"] == settings.default_library), None
    )

    if not default_library:
        # Create the default library if it doesn't exist
        response = httpx.post(
            f"{BASE_URL}/api/libraries",
            json={"name": settings.default_library, "folders": []},
        )
        if response.status_code != 200:
            print(
                f"Failed to create default library: {response.status_code} - {response.text}"
            )
            return None
        default_library = response.json()

        # Bind default plugins only when initializing the default library
        for plugin in settings.default_plugins:
            bind(default_library["id"], plugin)

    # Check if the library is empty
    if not default_library["folders"]:
        # Add the screenshots directory to the library
        screenshots_dir = Path(settings.resolved_screenshots_dir).resolve()
        folder = {
            "path": str(screenshots_dir),
            "last_modified_at": datetime.fromtimestamp(
                screenshots_dir.stat().st_mtime
            ).isoformat(),
        }
        response = httpx.post(
            f"{BASE_URL}/api/libraries/{default_library['id']}/folders",
            json={"folders": [folder]},
        )
        if response.status_code != 200:
            print(
                f"Failed to add screenshots directory: {response.status_code} - {response.text}"
            )
            return None
        print(f"Added screenshots directory: {screenshots_dir}")

    return default_library


@app.command("scan")
def scan_default_library(
    force: bool = typer.Option(False, "--force", help="Force update all indexes"),
    path: str = typer.Argument(None, help="Path to scan within the library"),
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
):
    """
    Scan the screenshots directory and add it to the library if empty.
    """
    from .cmds.library import scan

    default_library = get_or_create_default_library()
    if not default_library:
        return

    print(f"Scanning library: {default_library['name']}")
    scan(
        default_library["id"],
        path=path,
        plugins=plugins,
        folders=folders,
        force=force,
        batch_size=batch_size,
    )


@app.command("reindex")
def reindex_default_library(
    force: bool = typer.Option(
        False, "--force", help="Force recreate FTS and vector tables before reindexing"
    ),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
):
    """
    Reindex the default library for memos.
    """
    from .cmds.library import reindex

    # Get the default library
    response = httpx.get(f"{BASE_URL}/api/libraries")
    if response.status_code != 200:
        print(f"Failed to retrieve libraries: {response.status_code} - {response.text}")
        return

    libraries = response.json()
    default_library = next(
        (lib for lib in libraries if lib["name"] == settings.default_library), None
    )

    if not default_library:
        print("Default library does not exist.")
        return

    # Reindex the library
    print(f"Reindexing library: {default_library['name']}")
    reindex(default_library["id"], force=force, folders=None, batch_size=batch_size)


@app.command("record")
def record(
    threshold: int = typer.Option(4, help="Threshold for image similarity"),
    base_dir: str = typer.Option(None, help="Base directory for screenshots"),
    once: bool = typer.Option(False, help="Run once and exit"),
):
    """Record screenshots of the screen."""
    from .service_manager import register_service_signals, remove_pid_file
    
    # 只有持续运行模式才需要注册信号处理
    if not once:
        register_service_signals("record")
    
    try:
        from .record import (
            run_screen_recorder_once,
            run_screen_recorder,
            load_previous_hashes,
        )

        base_dir = (
            os.path.expanduser(base_dir) if base_dir else settings.resolved_screenshots_dir
        )
        previous_hashes = load_previous_hashes(base_dir)

        if once:
            run_screen_recorder_once(threshold, base_dir, previous_hashes)
        else:
            # Log the record interval
            logging.info(f"Record interval set to {settings.record_interval} seconds.")
            while True:
                try:
                    run_screen_recorder(threshold, base_dir, previous_hashes)
                except Exception as e:
                    logging.error(
                        f"Critical error occurred, program will restart in 10 seconds: {str(e)}"
                    )
                    time.sleep(10)
    finally:
        # 只有持续运行模式才需要清理PID文件
        if not once:
            remove_pid_file("record")


@app.command("watch")
def watch_default_library(
    rate_window_size: int = typer.Option(
        settings.watch.rate_window_size,
        "--rate-window",
        "-rw",
        help="Window size for rate calculation",
    ),
    sparsity_factor: float = typer.Option(
        settings.watch.sparsity_factor,
        "--sparsity-factor",
        "-sf",
        help="Sparsity factor for file processing",
    ),
    processing_interval: int = typer.Option(
        settings.watch.processing_interval,
        "--processing-interval",
        "-pi",
        help="Processing interval for file processing",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Watch the default library for file changes and sync automatically."""
    from .service_manager import register_service_signals, remove_pid_file
    
    # 注册信号处理
    register_service_signals("watch")
    
    try:
        typer.echo(f"Watch settings:")
        typer.echo(f"  rate_window_size: {rate_window_size}")
        typer.echo(f"  sparsity_factor: {sparsity_factor}")
        typer.echo(f"  processing_interval: {processing_interval}")

        from .cmds.library import watch

        # Add retry logic for getting default library
        while True:
            default_library = get_or_create_default_library()
            if default_library:
                break
            typer.echo("Failed to get or create default library. Retrying in 5 seconds...")
            time.sleep(5)

        watch(
            default_library["id"],
            folders=None,
            rate_window_size=rate_window_size,
            sparsity_factor=sparsity_factor,
            processing_interval=processing_interval,
            verbose=verbose,
        )
    finally:
        remove_pid_file("watch")


def get_python_path():
    return sys.executable


def generate_windows_bat():
    memos_dir = settings.resolved_base_dir
    python_path = get_python_path()
    pythonw_path = python_path.replace("python.exe", "pythonw.exe")
    conda_prefix = os.environ.get("CONDA_PREFIX")
    log_dir = memos_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if conda_prefix:
        # If we're in a Conda environment
        activate_path = os.path.join(conda_prefix, "Scripts", "activate.bat")
        content = f"""@echo off
call "{activate_path}"
start /B "" "{pythonw_path}" -m memos.commands record > "{log_dir / 'record.log'}" 2>&1
start /B "" "{pythonw_path}" -m memos.commands serve > "{log_dir / 'serve.log'}" 2>&1
REM watch service will automatically retry until serve is ready
start /B "" "{pythonw_path}" -m memos.commands watch > "{log_dir / 'watch.log'}" 2>&1
"""
    else:
        # If we're not in a Conda environment
        content = f"""@echo off
start /B "" "{pythonw_path}" -m memos.commands record > "{log_dir / 'record.log'}" 2>&1
start /B "" "{pythonw_path}" -m memos.commands serve > "{log_dir / 'serve.log'}" 2>&1
REM watch service will automatically retry until serve is ready
start /B "" "{pythonw_path}" -m memos.commands watch > "{log_dir / 'watch.log'}" 2>&1
"""

    bat_path = memos_dir / "launch.bat"
    with open(bat_path, "w") as f:
        f.write(content)
    return bat_path


def generate_launch_sh():
    memos_dir = settings.resolved_base_dir
    python_path = get_python_path()
    content = f"""#!/bin/bash
# activate current python environment
if [ -f "$(dirname "$python_path")/activate" ]; then
    source "$(dirname "$python_path")/activate"
fi

# run memos record
{python_path} -m memos.commands record &

# run memos serve
{python_path} -m memos.commands serve &

# run memos watch (watch service will automatically retry until serve is ready)
{python_path} -m memos.commands watch &

# wait for all background processes
wait
"""
    launch_sh_path = memos_dir / "launch.sh"
    with open(launch_sh_path, "w") as f:
        f.write(content)
    launch_sh_path.chmod(0o755)


def setup_windows_autostart(bat_path):
    import win32com.client

    startup_folder = (
        Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = startup_folder / "Memos.lnk"

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(bat_path)
    shortcut.WorkingDirectory = str(bat_path.parent)
    shortcut.WindowStyle = 7  # Minimized
    shortcut.save()


def generate_plist():
    memos_dir = settings.resolved_base_dir
    python_dir = os.path.dirname(get_python_path())
    log_dir = memos_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.memos</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{memos_dir}/launch.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/memos.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/memos.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{python_dir}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
"""
    plist_dir = Path.home() / "Library/LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.user.memos.plist"
    with open(plist_path, "w") as f:
        f.write(plist_content)
    return plist_path


def is_service_loaded(service_name):
    try:
        result = subprocess.run(
            ["launchctl", "list", service_name],
            capture_output=True,
            text=True,
            check=True,
        )
        return "0" in result.stdout
    except subprocess.CalledProcessError:
        return False


def load_plist(plist_path):
    service_name = "com.user.memos"

    if is_service_loaded(service_name):
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False)

    subprocess.run(["launchctl", "load", str(plist_path)], check=True)


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


def remove_windows_autostart():
    startup_folder = (
        Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = startup_folder / "Memos.lnk"

    if shortcut_path.exists():
        shortcut_path.unlink()
        return True
    return False


@app.command()
def disable():
    """Disable memos from running at startup"""
    if is_windows():
        if remove_windows_autostart():
            typer.echo(
                "Removed Memos shortcut from startup folder. Memos will no longer run at startup."
            )
        else:
            typer.echo(
                "Memos shortcut not found in startup folder. Memos is not set to run at startup."
            )
    elif is_macos():
        plist_path = Path.home() / "Library/LaunchAgents/com.user.memos.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=True)
            plist_path.unlink()
            typer.echo(
                "Unloaded and removed plist file. Memos will no longer run at startup."
            )
        else:
            typer.echo("Plist file does not exist. Memos is not set to run at startup.")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def enable():
    """Enable memos to run at startup (without starting it immediately)"""
    if not sys.executable:
        typer.echo("Error: Unable to detect Python environment.")
        raise typer.Exit(code=1)

    memos_dir = settings.resolved_base_dir
    memos_dir.mkdir(parents=True, exist_ok=True)

    if is_windows():
        bat_path = generate_windows_bat()
        typer.echo(f"Generated launch script at {bat_path}")
        setup_windows_autostart(bat_path)
        typer.echo("Created startup shortcut for Windows.")
    elif is_macos():
        launch_sh_path = generate_launch_sh()
        typer.echo(f"Generated launch script at {launch_sh_path}")
        plist_path = generate_plist()
        typer.echo(f"Generated plist file at {plist_path}")
        load_plist(plist_path)
        typer.echo(
            "Loaded plist file. Memos is started and will run at next startup or when 'start' command is used."
        )
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def ps():
    """Show the status of Memos processes"""
    services = ["serve", "watch", "record"]
    table_data = []

    for service in services:
        processes = [
            p
            for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"])
            if "python" in p.info["name"].lower()
            and p.info["cmdline"] is not None
            and "memos.commands" in p.info["cmdline"]
            and service in p.info["cmdline"]
        ]

        if processes:
            for process in processes:
                create_time = datetime.fromtimestamp(
                    process.info["create_time"]
                ).strftime("%Y-%m-%d %H:%M:%S")
                running_time = str(
                    timedelta(seconds=int(time.time() - process.info["create_time"]))
                )
                table_data.append(
                    [service, "Running", process.info["pid"], create_time, running_time]
                )
        else:
            table_data.append([service, "Not Running", "-", "-", "-"])

    headers = ["Name", "Status", "PID", "Started At", "Running For"]
    typer.echo(tabulate(table_data, headers=headers, tablefmt="plain"))


@app.command()
def stop(
    service: str = typer.Argument("all", help="Service to stop: serve, record, watch, or all")
):
    """Stop specific Memos service or all services"""
    from .service_manager import stop_service
    
    if service == "all":
        # 停止所有服务
        for svc in ["watch", "record", "serve"]:  # 注意停止顺序
            if stop_service(svc):
                typer.echo(f"已停止{svc}服务")
            else:
                typer.echo(f"停止{svc}服务失败")
    elif service in ["serve", "record", "watch"]:
        if stop_service(service):
            typer.echo(f"已停止{service}服务")
        else:
            typer.echo(f"停止{service}服务失败")
    else:
        typer.echo(f"未知服务: {service}")


@app.command()
def start(
    service: str = typer.Argument("all", help="Service to start: serve, record, watch, or all")
):
    """Start specific Memos service or all services"""
    from .service_manager import start_service
    
    if service == "all":
        # 启动所有服务
        for svc in ["serve", "record", "watch"]:
            if start_service(svc):
                typer.echo(f"已启动{svc}服务")
            else:
                typer.echo(f"启动{svc}服务失败或已在运行")
    elif service in ["serve", "record", "watch"]:
        if start_service(service):
            typer.echo(f"已启动{service}服务")
        else:
            typer.echo(f"启动{service}服务失败或已在运行")
    else:
        typer.echo(f"未知服务: {service}")


@app.command()
def config():
    """Show current configuration settings"""
    display_config()


@app.command("version")
def version():
    """Output the package version, Python version, and platform information in a single line."""
    # Get Python version
    python_version = sys.version.split()[0]  # Only get the version number

    # Get platform information
    system = platform.system()
    machine = platform.machine()

    # Output all information in a single line
    typer.echo(
        f"Package: {__version__}, Python: {python_version}, System: {system.lower()}/{machine.lower()}"
    )


@app.command("migrate")
def migrate_sqlite_to_pg(
    sqlite_url: str = typer.Option(..., "--sqlite-url", help="SQLite database URL (e.g., sqlite:///path/to/db.sqlite)"),
    pg_url: str = typer.Option(..., "--pg-url", help="PostgreSQL database URL (e.g., postgresql://user:pass@localhost/dbname)"),
    batch_size: int = typer.Option(1000, "--batch-size", "-bs", help="Number of records to migrate in each batch"),
):
    """Migrate data from SQLite to PostgreSQL (excluding FTS and vector tables)"""
    # Ask for user confirmation
    typer.echo("WARNING: This will completely erase all data in the PostgreSQL database.")
    if not typer.confirm("Do you want to continue?"):
        typer.echo("Migration cancelled.")
        raise typer.Exit(code=0)

    from sqlalchemy import create_engine, MetaData
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import func
    from sqlalchemy.sql import text
    from .models import (
        LibraryModel, FolderModel, EntityModel, TagModel, 
        EntityTagModel, EntityMetadataModel, PluginModel,
        LibraryPluginModel, EntityPluginStatusModel
    )
    from .databases.initializers import init_database
    from .migrations import run_migrations

    # Reorder tables to handle foreign key dependencies
    TABLES_TO_MIGRATE = [
        # Base tables (no foreign key dependencies)
        LibraryModel,
        PluginModel,
        TagModel,
        
        # Tables with single foreign key dependencies
        LibraryPluginModel,  # depends on libraries and plugins
        FolderModel,         # depends on libraries
        EntityModel,         # depends on libraries and folders
        
        # Tables with multiple foreign key dependencies
        EntityTagModel,      # depends on entities and tags
        EntityMetadataModel, # depends on entities
        EntityPluginStatusModel, # depends on entities and plugins
    ]

    def copy_instance(obj):
        """Create a copy of an object without SQLAlchemy state"""
        mapper = obj.__mapper__
        new_instance = obj.__class__()
        
        for column in mapper.columns:
            setattr(new_instance, column.key, getattr(obj, column.key))
        
        return new_instance

    def reset_sequence(session, table):
        """Reset PostgreSQL sequence before inserting data"""
        if not hasattr(table, 'id'):
            return
        
        table_name = table.__tablename__
        seq_name = f"{table_name}_id_seq"
        
        # Reset sequence to 1
        session.execute(text(f"ALTER SEQUENCE {seq_name} RESTART WITH 1"))
        session.commit()

    def update_sequence(session, table):
        """Update PostgreSQL sequence after data migration"""
        if not hasattr(table, 'id'):
            return
        
        table_name = table.__tablename__
        seq_name = f"{table_name}_id_seq"
        
        # Get the maximum ID from the table
        max_id = session.query(func.max(table.id)).scalar() or 0
        
        # Set the sequence to the next value after max_id
        session.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))
        session.commit()

    try:
        # Create database connections
        sqlite_engine = create_engine(sqlite_url)
        pg_engine = create_engine(pg_url)
        
        # Drop all existing tables in PostgreSQL
        typer.echo("Dropping existing tables in PostgreSQL...")
        metadata = MetaData()
        metadata.reflect(bind=pg_engine)
        metadata.drop_all(bind=pg_engine)
        
        # Initialize PostgreSQL database from scratch
        typer.echo("Initializing PostgreSQL database...")
        # Temporarily modify settings.database_path instead of database_url
        original_database_path = settings.database_path
        settings.database_path = pg_url
        
        try:
            db_success = init_database(settings)
            if not db_success:
                typer.echo("Failed to initialize PostgreSQL database.")
                raise typer.Exit(code=1)
            
            # Run migrations
            typer.echo("Running migrations...")
            run_migrations()
            
            # Create sessions after initialization
            SQLiteSession = sessionmaker(bind=sqlite_engine)
            PGSession = sessionmaker(bind=pg_engine)
            
            sqlite_session = SQLiteSession()
            pg_session = PGSession()


            # Clear any default data created during initialization
            typer.echo("Clearing initialization data...")
            for model in reversed(TABLES_TO_MIGRATE):
                pg_session.query(model).delete()
            pg_session.commit()

            # Find the longest table name for alignment
            max_name_length = max(len(model.__tablename__) for model in TABLES_TO_MIGRATE)

            # Migrate each table
            for model in TABLES_TO_MIGRATE:
                table_name = model.__tablename__
                typer.echo(f"Migrating {table_name:<{max_name_length}}...")
                
                # Reset sequence before migration
                reset_sequence(pg_session, model)
                
                # Get total count
                total_count = sqlite_session.query(model).count()
                if total_count == 0:
                    typer.echo(f"No data found in {table_name:<{max_name_length}}, skipping...")
                    continue

                # Process in batches
                processed = 0
                with typer.progressbar(
                    length=total_count,
                    label=f"Migrating {table_name:<{max_name_length}}"
                ) as progress:
                    while processed < total_count:
                        # Get batch of records from source
                        batch = (
                            sqlite_session.query(model)
                            .offset(processed)
                            .limit(batch_size)
                            .all()
                        )
                        
                        try:
                            # Copy and insert records
                            for record in batch:
                                new_record = copy_instance(record)
                                pg_session.add(new_record)
                            
                            # Commit batch
                            pg_session.commit()
                        except Exception as e:
                            pg_session.rollback()
                            typer.echo(f"Error migrating batch in {table_name}: {str(e)}")
                            raise
                        
                        # Update progress
                        processed += len(batch)
                        progress.update(len(batch))

                # Update sequence after migrating each table
                update_sequence(pg_session, model)
                
                typer.echo(f"Successfully migrated {processed} records from {table_name:<{max_name_length}}")

            typer.echo("Migration completed successfully!")
            
        finally:
            # Restore original database path
            settings.database_path = original_database_path

    except Exception as e:
        pg_session.rollback()
        typer.echo(f"Error during migration: {str(e)}", err=True)
        raise typer.Exit(code=1)
    
    finally:
        try:
            sqlite_session.close()
            pg_session.close()
        except:
            pass


@app.command()
def restart(
    service: str = typer.Argument("all", help="Service to restart: serve, record, watch, or all")
):
    """Restart specific Memos service or all services"""
    from .service_manager import restart_service, restart_processes
    
    if service == "all":
        # 重启所有服务
        results = restart_processes({"watch": True, "record": True, "serve": True})
        for svc, success in results.items():
            typer.echo(f"{'已' if success else '未'}重启{svc}服务")
    elif service in ["serve", "record", "watch"]:
        success = restart_service(service)
        typer.echo(f"{'已' if success else '未'}重启{service}服务")
    else:
        typer.echo(f"未知服务: {service}")


if __name__ == "__main__":
    app()
