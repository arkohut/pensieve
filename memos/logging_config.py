import logging
import logging.config
import os
from datetime import datetime

class DetailedFormatter(logging.Formatter):
    def format(self, record):
        # Add log_type prefix if present
        if hasattr(record, 'log_type'):
            if record.log_type == 'bg':
                record.msg = f"[bg] {record.msg}"
        return super().format(record)

# Default logging configuration for server.py and other modules
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            '()': DetailedFormatter,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}

def setup_logging(log_dir=None):
    """
    Setup logging configuration with optional file output.
    This function allows for dynamic configuration of logging,
    particularly useful for command-line tools that need file output.
    """
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        
    # Start with a copy of the default config
    config = LOGGING_CONFIG.copy()
    
    if log_dir:
        log_file = os.path.join(log_dir, f'memos_{datetime.now().strftime("%Y%m%d")}.log')
        config['handlers']['file'] = {
            'class': 'logging.FileHandler',
            'formatter': 'detailed',
            'filename': log_file,
            'mode': 'a'
        }
        config['root']['handlers'] = ['console', 'file']
    
    logging.config.dictConfig(config)
    return logging.getLogger('memos')