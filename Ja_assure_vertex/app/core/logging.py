import logging
import sys

def setup_logging():
    logger = logging.getLogger("ja_assure")
    logger.setLevel(logging.INFO)
    
    # Check if handlers already exist to avoid duplicate logs in some environments
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logging()
