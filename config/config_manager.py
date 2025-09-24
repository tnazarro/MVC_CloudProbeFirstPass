import json
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_data = None
        print("ConfigManager created!")  # Just to see it working
    
    def is_loaded(self):
        return False  # For now, always return False