# config/config_manager.py
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config_data: Optional[Dict[str, Any]] = None
        
        # Try to load on creation
        self._load_config()
    
    def _load_config(self) -> bool:
        """Try to load the config file."""
        if not self.config_path.exists():
            load_error = f"Config file not found: {self.config_path}"
            logger.warning(load_error)
            print(f"⚠️  {load_error}")
            return False
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            logger.info(f"✅ Config loaded from {self.config_path}")
            print(f"✅ Config loaded! Version: {self.config_data.get('version', 'unknown')}")
            return True
            
        except json.JSONDecodeError as e:
            load_error = f"Invalid JSON: {e}"
            logger.error(load_error)
            print(f"❌ {load_error}")
            return False
        except Exception as e:
            load_error = f"Error loading config: {e}"
            logger.error(load_error)
            print(f"❌ {load_error}")
            return False
    
    def is_loaded(self) -> bool:
        """Check if config loaded successfully."""
        return self.config_data is not None
    
    def get_instrument_config(self, instrument_type: str) -> Optional[Dict[str, Any]]:
        """
        Look up config for an instrument type.
        Returns the config dict if found, None otherwise.
        """
        if not self.is_loaded():
            print(f"⚠️  Config not loaded, can't look up {instrument_type}")
            return None
        
        # Search through configs
        for config in self.config_data.get('configs', []):
            if config.get('instrument') == instrument_type:
                print(f"✅ Found config for {instrument_type}!")
                print(f"   - Bin count: {config.get('calibration', {}).get('bins')}")
                print(f"   - Size column: {config.get('variants', [{}])[0].get('pbpKey')}")
                return config
        
        print(f"⚠️  No config found for {instrument_type}")
        return None