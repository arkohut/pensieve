import os
import shutil
from pathlib import Path
from typing import Tuple, Type, List
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from pydantic import BaseModel, SecretStr, field_validator
import yaml
from collections import OrderedDict
import typer
from datetime import datetime


class VLMSettings(BaseModel):
    modelname: str = "minicpm-v"
    endpoint: str = "http://localhost:11434"
    token: SecretStr = SecretStr("")
    concurrency: int = 8
    # some vlm models do not support webp
    force_jpeg: bool = True
    # prompt for vlm to extract caption
    prompt: str = "请帮描述这个图片中的内容，包括画面格局、出现的视觉元素等"
    # whether to enable the VLM plugin
    enabled: bool = True


class OCRSettings(BaseModel):
    # will by ignored if use_local is True
    endpoint: str = "http://localhost:5555/predict"
    token: SecretStr = SecretStr("")
    concurrency: int = 8
    use_local: bool = True
    force_jpeg: bool = False
    # whether to enable the OCR plugin
    enabled: bool = True


class EmbeddingSettings(BaseModel):
    num_dim: int = 768
    # will be ignored if use_local is True
    endpoint: str = "http://localhost:11434/v1/embeddings"
    model: str = "jinaai/jina-embeddings-v2-base-zh"
    # pull model from huggingface by default, make it true if you want to pull from modelscope
    use_modelscope: bool = False
    use_local: bool = True
    token: SecretStr = SecretStr("")


class WatchSettings(BaseModel):
    rate_window_size: int = 10
    sparsity_factor: float = 3.0
    processing_interval: int = 12
    idle_timeout: int = 30  # seconds before marking state as idle
    idle_process_interval: List[str] = ["00:00", "07:00"]  # time interval for processing skipped files

    @field_validator("idle_process_interval")
    @classmethod
    def validate_idle_process_interval(cls, v):
        if not isinstance(v, list) or len(v) != 2:
            raise ValueError("idle_process_interval must be a list of exactly 2 time strings")

        try:
            start_time = datetime.strptime(v[0], "%H:%M").time()
            end_time = datetime.strptime(v[1], "%H:%M").time()
        except ValueError as e:
            raise ValueError(f"Invalid time format in idle_process_interval. Must be HH:MM format: {str(e)}")

        # Convert times to minutes since midnight for easier comparison
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        # If end time is less than start time, it means the interval crosses midnight
        # For example: ["23:00", "07:00"] is valid
        # But ["07:00", "02:00"] is not valid as it's ambiguous
        if end_minutes < start_minutes:
            # For crossing midnight, we only allow the start time to be after 12:00 (noon)
            # This helps avoid ambiguous intervals
            if start_time.hour < 12:
                raise ValueError(
                    "For intervals crossing midnight, start time must be after 12:00 "
                    "to avoid ambiguity (e.g. '23:00-07:00' is valid, but '07:00-02:00' is not)"
                )
        elif end_minutes == start_minutes:
            raise ValueError("Start time and end time cannot be the same")

        return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(Path.home() / ".memos" / "config.yaml"),
        yaml_file_encoding="utf-8",
        env_prefix="MEMOS_",
        extra="ignore",
    )

    base_dir: str = "~/.memos"
    database_path: str = "database.db"
    default_library: str = "screenshots"
    screenshots_dir: str = "screenshots"
    facet: bool = False

    # Server settings
    server_host: str = "127.0.0.1"
    server_port: int = 8839

    # VLM plugin settings
    vlm: VLMSettings = VLMSettings()

    # OCR plugin settings
    ocr: OCRSettings = OCRSettings()

    # Embedding settings
    embedding: EmbeddingSettings = EmbeddingSettings()

    auth_username: str = ""
    auth_password: SecretStr = SecretStr("")

    default_plugins: List[str] = ["builtin_ocr"]

    record_interval: int = 4

    # App blacklist for recording
    app_blacklist: List[str] = []

    watch: WatchSettings = WatchSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    @property
    def resolved_base_dir(self) -> Path:
        return Path(self.base_dir).expanduser().resolve()

    @property
    def resolved_database_path(self) -> Path:
        # Only resolve path for SQLite database with relative path
        if not any(self.database_path.startswith(prefix) for prefix in ["postgresql://", "sqlite://"]):
            return self.resolved_base_dir / self.database_path
        return None

    @property
    def resolved_screenshots_dir(self) -> Path:
        return self.resolved_base_dir / self.screenshots_dir

    @property
    def database_url(self) -> str:
        # If database_path starts with a URL scheme, use it directly
        if self.database_path.startswith(("postgresql://", "sqlite://")):
            return self.database_path
        # Otherwise treat it as a SQLite database path relative to base_dir
        return f"sqlite:///{self.resolved_database_path}"

    @property
    def is_sqlite(self) -> bool:
        return self.database_path.startswith("sqlite://") or not self.database_path.startswith("postgresql://")

    @property
    def server_endpoint(self) -> str:
        host = "127.0.0.1" if self.server_host == "0.0.0.0" else self.server_host
        return f"http://{host}:{self.server_port}"


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


yaml.add_representer(OrderedDict, dict_representer)


# Custom representer for SecretStr
def secret_str_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.get_secret_value())


# Custom constructor for SecretStr
def secret_str_constructor(loader, node):
    value = loader.construct_scalar(node)
    return SecretStr(value)


# Register the representer and constructor only for specific fields
yaml.add_representer(SecretStr, secret_str_representer)


def create_default_config():
    # the config file is always created in the home directory
    # not influenced by the base_dir setting
    config_path = Path.home() / ".memos" / "config.yaml"
    if not config_path.exists():
        template_path = Path(__file__).parent / "default_config.yaml"
        os.makedirs(config_path.parent, exist_ok=True)
        shutil.copy(template_path, config_path)
        print(f"Created default configuration at {config_path}")


# Create default config if it doesn't exist
create_default_config()

settings = Settings()

# Define the default database path
os.makedirs(settings.resolved_base_dir, exist_ok=True)


# Function to get the database path from environment variable or default
def get_database_path():
    return str(settings.resolved_database_path)


def format_value(value, indent_level=0):
    indent = "  " * indent_level
    if isinstance(value, dict):
        if not value:
            return "{}"
        formatted_items = []
        for k, v in value.items():
            formatted_value = format_value(v, indent_level + 1)
            if isinstance(v, (dict, list, tuple)) and v:
                formatted_items.append(f"{indent}  {k}:\n{formatted_value}")
            else:
                formatted_items.append(f"{indent}  {k}: {formatted_value}")
        return "\n".join(formatted_items)
    elif isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        formatted_items = [f"{indent}  - {format_value(item, indent_level + 1)}" for item in value]
        return "\n".join(formatted_items)
    elif isinstance(value, SecretStr):
        return "********"  # Hide the actual value of SecretStr
    else:
        return str(value)


def display_config():
    settings = Settings()
    config_dict = settings.model_dump()

    for key, value in config_dict.items():
        formatted_value = format_value(value)
        
        if key in ["base_dir", "database_path", "screenshots_dir"]:
            resolved_value = getattr(settings, f"resolved_{key}")
            typer.echo(f"{key}:")
            typer.echo(f"  value: {value}")
            typer.echo(f"  resolved: {resolved_value}")
        else:
            if isinstance(value, (dict, list, tuple)) and value:
                typer.echo(f"{key}:")
                typer.echo(formatted_value)
            else:
                typer.echo(f"{key}: {formatted_value}")


def load_config() -> Settings:
    """Load configuration from the config file"""
    return Settings()

def save_config(config_dict: dict):
    """Save configuration to the config file"""
    # Get the path to the config file
    config_path = Path.home() / ".memos" / "config.yaml"
    
    # Convert SecretStr values appropriately
    for section_name, section in config_dict.items():
        if isinstance(section, dict):
            for key, value in section.items():
                if isinstance(value, str) and value == "********":
                    # Skip masked password fields - keep the original value
                    section_obj = getattr(settings, section_name, None)
                    if section_obj and hasattr(section_obj, key):
                        original_value = getattr(section_obj, key)
                        section[key] = original_value
    
    # Write to file
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, sort_keys=False, default_flow_style=False)

def categorize_settings_by_restart():
    """Categorize which settings require restart of which components
    
    Returns a dictionary mapping setting paths to affected components.
    Example: {"database_path": ["serve"], "record_interval": ["record"]}
    """
    return {
        # Core configuration affecting all services
        "base_dir": ["serve", "watch", "record"],  # Changes to the base directory affect all services
        "screenshots_dir": ["serve", "record", "watch"],     # Changes to the screenshots directory affect recording and monitoring services
        
        # Configuration affecting only the server
        "database_path": ["serve"],     # Changes to the database path
        "server_host": ["serve"],       # Changes to the server host
        "server_port": ["serve"],       # Changes to the server port
        "auth_username": ["serve"],     # Changes to authentication information
        "auth_password": ["serve"],
        "facet": ["serve"],            # Changes to the search facet feature
        
        # Configuration affecting only the recording service
        "record_interval": ["record"],  # Changes to the recording interval
        "app_blacklist": ["record"],    # Changes to the app blacklist
        
        # Configuration affecting only the monitoring service
        "watch.rate_window_size": ["watch"],
        "watch.sparsity_factor": ["watch"],
        "watch.processing_interval": ["watch"],
        "watch.idle_timeout": ["watch"],
        "watch.idle_process_interval": ["watch"],
        
        # Plugin-related configuration
        "vlm": ["serve"],
        "vlm.enabled": ["serve"],       # Changes to VLM plugin enabled flag
        "ocr": ["serve"],
        "ocr.enabled": ["serve"],       # Changes to OCR plugin enabled flag
        "embedding": ["serve"],
        "default_plugins": ["serve"],
    }

def apply_config_updates(current_config: dict, updates: dict):
    """Apply updates to the configuration
    
    Returns the updated config dict and a dict indicating which components need restart
    """
    restart_required = {"serve": False, "watch": False, "record": False}
    restart_map = categorize_settings_by_restart()
    
    # Helper function to apply updates recursively
    def apply_updates_recursive(current, updates, path=""):
        for key, value in updates.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check if this setting requires restart
            if current_path in restart_map:
                for component in restart_map[current_path]:
                    restart_required[component] = True
            
            # If this is a nested dict, recursively update
            if isinstance(value, dict) and key in current and isinstance(current[key], dict):
                apply_updates_recursive(current[key], value, current_path)
            else:
                # Check for masked password values
                if isinstance(value, str) and value == "********":
                    # Skip - keep original value
                    continue
                
                # Direct update
                current[key] = value
    
    # Apply updates
    apply_updates_recursive(current_config, updates)
    
    return current_config, restart_required

def restart_processes(components: dict):
    """Restart processes using the service_manager module"""
    from .service_manager import api_restart_services
    return api_restart_services(components)
