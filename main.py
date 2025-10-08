# main.py
"""
Main entry point for the Cloud Probe Data Analyzer application.
"""

import tkinter as tk
from gui.main_window import MainWindow
from utils.logger import setup_logger
import logging

def main():
    """Initialize and run the application."""
    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)
    logger.info("Starting Cloud Probe Data Analyzer")
    
    # Create and run the application
    root = tk.Tk()
    app = MainWindow(root)
    
    try:
        root.mainloop()
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        logger.info("Application closed")

if __name__ == "__main__":
    main()
    