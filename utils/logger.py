# utils/logger.py
"""
Logging configuration for the application.
"""

import logging
import os
from datetime import datetime

def setup_logger(log_level=logging.INFO, log_file=None):
    """
    Setup application logging.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Optional log file path
    """
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Default log file with timestamp
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"logs/particle_analyzer_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Set matplotlib logging to WARNING to reduce noise
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")