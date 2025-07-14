# config/constants.py
"""
Application constants and configuration values.
"""

# File types supported
SUPPORTED_FILE_TYPES = [
    ("CSV files", "*.csv"),
    ("All files", "*.*")
]

# Default plot settings
DEFAULT_BIN_COUNT = 50
MIN_BIN_COUNT = 10
MAX_BIN_COUNT = 1000

# Column name mappings (common names for particle size data)
SIZE_COLUMN_NAMES = ['size', 'diameter', 'particle_size', 'Size', 'Diameter']
FREQUENCY_COLUMN_NAMES = ['frequency', 'count', 'number', 'Frequency', 'Count']

# Random data generation settings
RANDOM_DATA_BOUNDS = {
    'size_min': 0.1,      # Minimum particle size
    'size_max': 100.0,    # Maximum particle size
    'freq_min': 1,        # Minimum frequency
    'freq_max': 1000,     # Maximum frequency
    'default_n': 500      # Default number of data points
}

# Plot settings
PLOT_WIDTH = 8
PLOT_HEIGHT = 6
PLOT_DPI = 100

