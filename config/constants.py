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
MIN_BIN_COUNT = 1
MAX_BIN_COUNT = 4095

# Column name mappings (common names for particle size data)
SIZE_COLUMN_NAMES = ['size', 'diameter', 'particle_size', 'Size', 'Diameter']
FREQUENCY_COLUMN_NAMES = ['frequency', 'count', 'number', 'Frequency', 'Count']

# Random data generation settings - OBSOLETE
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

# CSV file encoding support (in order of likelihood for particle analysis data)
SUPPORTED_CSV_ENCODINGS = [
    'utf-8',           # Most common modern encoding
    'windows-1252',    # Common Windows encoding
    'iso-8859-1',      # Latin-1, common in scientific instruments
    'cp1252',          # Windows code page 1252
    'latin1'           # Alias for iso-8859-1, backup option
]

# Font configurations - centralized for easy modification
UI_FONTS = {
    'default': ('TkDefaultFont', 9, 'normal'),
    'bold': ('TkDefaultFont', 9, 'bold'),
    'small': ('TkDefaultFont', 8, 'normal'),
    'small_bold': ('TkDefaultFont', 8, 'bold'),
    'heading': ('TkDefaultFont', 10, 'bold'),
    'large_heading': ('TkDefaultFont', 11, 'bold'),
    'extra_large_heading': ('TkDefaultFont', 12, 'bold'),
    'courier': ('Courier', 9, 'normal'),
    'courier_small': ('Courier', 8, 'normal'),
}

# Backward compatibility - specific font references used in the codebase
FONT_INSTRUMENT_TYPE = UI_FONTS['bold']  # For instrument type labels
FONT_FILE_NAME = UI_FONTS['bold']        # For file name labels  
FONT_PROGRESS = UI_FONTS['heading']      # For progress text
FONT_PREVIEW_TEXT = UI_FONTS['courier']  # For preview text display
FONT_HINT_TEXT = UI_FONTS['small']       # For hint text
FONT_STATUS = UI_FONTS['small']          # For status labels
FONT_STATUS_LARGE = UI_FONTS['large_heading']  # For large status labels
