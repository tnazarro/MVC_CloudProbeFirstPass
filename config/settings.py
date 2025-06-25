# config/settings.py
"""
User settings and preferences.
"""

class AppSettings:
    """Manages application settings."""
    
    def __init__(self):
        self.last_directory = ""
        self.default_bin_count = 50
        self.auto_detect_columns = True
        self.plot_style = "seaborn-v0_8"  # matplotlib style
    
    def save_settings(self):
        """Save settings to file (implement later)."""
        pass
    
    def load_settings(self):
        """Load settings from file (implement later)."""
        pass