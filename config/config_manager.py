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
        """Try to load the config file, creating defaults if needed."""
        
        # Check if config file exists
        if not self.config_path.exists():
            logger.info(f"Config file not found: {self.config_path}")
            
            # Try to create default config
            if self._create_default_config():
                # Successfully created, now load it
                logger.info("Loading newly created config file")
                # Fall through to normal loading below
            else:
                # Couldn't create file, use in-memory defaults
                logger.warning("Using in-memory defaults (config file could not be created)")
                print(f"⚠️  Using built-in defaults (may be outdated)")
                self._load_defaults_to_memory()
                self.config_file_loaded = False
                return True
        
        # Load from file (either existing or newly created)
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            self.config_file_loaded = True
            logger.info(f"✅ Config loaded from {self.config_path}")
            print(f"✅ Config loaded! Version: {self.config_data.get('version', 'unknown')}")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            print(f"❌ Invalid JSON: {e}")
            self.config_file_loaded = False
            return False
            
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            print(f"❌ Error loading config: {e}")
            self.config_file_loaded = False
            return False
    
    def is_loaded(self) -> bool:
        """Check if config loaded successfully."""
        return self.config_data is not None

    def _create_default_config(self) -> bool:
        """
        Create a default config.json file with minimal example.
        
        Returns:
            bool: True if created successfully, False otherwise
        """
        default_config = {
            "version": "1.0",
            "configs": [
                {
                    "instrument": "CDP",
                    "calibration": {
                        "bins": 200
                    },
                    "variants": [
                        {
                            "pbpKey": "Size [counts]"
                        }
                    ]
                }
            ]
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            
            logger.info(f"Created default config file: {self.config_path}")
            print(f"✅ Created default config.json")
            return True
            
        except PermissionError:
            logger.warning(f"Permission denied creating config: {self.config_path}")
            print(f"⚠️  Cannot create config.json (permission denied)")
            return False
            
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            print(f"❌ Failed to create config.json: {e}")
            return False

    def _load_defaults_to_memory(self) -> None:
        """Load minimal defaults into memory when file can't be created."""
        #This happens if we can't create the file, but still need something
        self.config_data = {
            "version": "1.0",
            "configs": [
                {
                    "instrument": "CDP",
                    "calibration": {
                        "bins": 200
                    },
                    "variants": [
                        {
                            "pbpKey": "Size [counts]"
                        }
                    ]
                }
            ]
        }
        logger.info("Loaded default config to memory")

    def is_config_file_loaded(self) -> bool:
        """Check if config was loaded from actual file."""
        return self.config_file_loaded
    
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
    
    def _load_defaults_to_memory(self) -> None:
        """Load minimal defaults into memory when file can't be created."""
        self.config_data = {
            "version": "1.0",
            "configs": [
                {
                    "instrument": "CDP",
                    "calibration": {
                        "bins": 200
                    },
                    "variants": [
                        {
                            "pbpKey": "Size [counts]"
                        }
                    ]
                }
            ]
        }
        logger.info("Loaded default config to memory")