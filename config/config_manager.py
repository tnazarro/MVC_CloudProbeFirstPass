# config/config_manager.py
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from config.constants import CONFIG_VALIDATION_SCHEMA, DEFAULT_BIN_COUNT

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
            
            self._validate_all_configs()

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

    def _validate_all_configs(self) -> None:
        """
        Validate all instrument configurations against schema.
        Invalid configs are either fixed or removed.
        """
        if not self.config_data or 'configs' not in self.config_data:
            logger.warning("No configs array found in config file")
            return
        
        configs = self.config_data['configs']
        validated_configs = []
        
        for config in configs:
            # Check required instrument field first
            if not self._validate_instrument_field(config):
                # Skip this entire config - can't identify it
                continue
            
            instrument = config.get('instrument')
            logger.info(f"Validating config for {instrument}")
            
            # Validate and fix all other fields
            self._validate_config_fields(config, CONFIG_VALIDATION_SCHEMA, instrument)
            
            # Keep this config
            validated_configs.append(config)
        
        # Replace with validated list
        self.config_data['configs'] = validated_configs
        logger.info(f"Validated {len(validated_configs)} instrument configs")

    def _validate_instrument_field(self, config: dict) -> bool:
        """
        Validate the required instrument field.
        
        Args:
            config: Single instrument config dict
            
        Returns:
            bool: True if valid, False if missing/invalid (skip this config)
        """
        if 'instrument' not in config:
            logger.warning("Config missing required 'instrument' field - skipping")
            print("⚠️  Skipping config entry: missing instrument name")
            return False
        
        instrument = config['instrument']
        
        # Check type
        if not isinstance(instrument, str):
            logger.warning(f"Invalid instrument type: {type(instrument)} - skipping")
            print(f"⚠️  Skipping config entry: instrument must be string, got {type(instrument)}")
            return False
        
        # Check not empty
        if not instrument.strip():
            logger.warning("Config has empty instrument field - skipping")
            print("⚠️  Skipping config entry: instrument name is empty")
            return False
        
        return True
    
    def _validate_config_fields(self, config: dict, schema: dict, instrument: str = 'Unknown') -> None:
        """
        Validate and fix all fields in a config against schema.
        Modifies config dict in place.
        
        Args:
            config: Single instrument config dict
            schema: Schema definition dict
            instrument: Instrument name for logging (passed through recursion)
        """
        
        for field_name, field_schema in schema.items():
            # Skip 'instrument' - already validated
            if field_name == 'instrument':
                continue
            
            # Get current value (might not exist)
            current_value = config.get(field_name)
            
            # Validate this field
            validated_value = self._validate_single_field(
                value=current_value,
                field_name=field_name,
                field_schema=field_schema,
                instrument=instrument
            )
            
            # Update config with validated value
            if validated_value is not None:
                config[field_name] = validated_value
            elif field_name in config:
                # Field existed but is now invalid and has no default
                del config[field_name]

    def _validate_single_field(self, value, field_name: str, field_schema: dict, instrument: str):
        """
        Validate a single field against its schema rules.
        
        Args:
            value: Current field value (may be None)
            field_name: Name of the field being validated
            field_schema: Schema rules for this field
            instrument: Instrument name (for logging)
            
        Returns:
            Validated/fixed value, or None if should be removed
        """
        required = field_schema.get('required', False)
        expected_type = field_schema.get('type')
        default_value = field_schema.get('default')
        
        # Handle missing field
        if value is None:
            if required:
                logger.warning(f"{instrument}: Required field '{field_name}' missing, using default: {default_value}")
                print(f"⚠️  {instrument}: Missing '{field_name}', using default: {default_value}")
                return default_value
            else:
                # Optional and missing - return default if available
                return default_value
        
        # Check type
        if expected_type and not isinstance(value, expected_type):
            logger.warning(f"{instrument}: Invalid type for '{field_name}': expected {expected_type.__name__}, got {type(value).__name__}")
            print(f"⚠️  {instrument}: Invalid '{field_name}' type, using default: {default_value}")
            return default_value
        
        # Type-specific validation
        if expected_type == int:
            return self._validate_int_field(value, field_name, field_schema, instrument, default_value)
        elif expected_type == str:
            return self._validate_str_field(value, field_name, field_schema, instrument, default_value)
        elif expected_type == dict:
            return self._validate_dict_field(value, field_name, field_schema, instrument)
        elif expected_type == list:
            return self._validate_list_field(value, field_name, field_schema, instrument)
        
        # No specific validation needed
        return value
    
    def _validate_int_field(self, value: int, field_name: str, field_schema: dict, 
                        instrument: str, default_value) -> int:
        """Validate integer field with min/max constraints."""
        min_val = field_schema.get('min')
        max_val = field_schema.get('max')
        
        # Check min constraint
        if min_val is not None and value < min_val:
            logger.warning(f"{instrument}: '{field_name}' value {value} below minimum {min_val}, using default: {default_value}")
            print(f"⚠️  {instrument}: '{field_name}' too small ({value} < {min_val}), using default: {default_value}")
            return default_value
        
        # Check max constraint
        if max_val is not None and value > max_val:
            logger.warning(f"{instrument}: '{field_name}' value {value} above maximum {max_val}, using default: {default_value}")
            print(f"⚠️  {instrument}: '{field_name}' too large ({value} > {max_val}), using default: {default_value}")
            return default_value
        
        # Valid
        return value
    
    def _validate_str_field(self, value: str, field_name: str, field_schema: dict,
                       instrument: str, default_value) -> str:
        """Validate string field with length constraints."""
        min_length = field_schema.get('min_length')
        
        # Check minimum length
        if min_length is not None and len(value.strip()) < min_length:
            logger.warning(f"{instrument}: '{field_name}' too short (min {min_length}), using default: {default_value}")
            print(f"⚠️  {instrument}: '{field_name}' empty or too short, using default: {default_value}")
            return default_value
        
        # Valid
        return value
    
    def _validate_dict_field(self, value: dict, field_name: str, field_schema: dict,
                        instrument: str) -> dict:
        """Validate nested dictionary against nested schema."""
        nested_schema = field_schema.get('schema')
        
        if not nested_schema:
            # No nested validation rules
            return value
        
        # Recursively validate nested fields
        self._validate_config_fields(value, nested_schema, instrument)
        
        return value
    
    def _validate_list_field(self, value: list, field_name: str, field_schema: dict,
                        instrument: str) -> list:
        """Validate list and its items against item schema."""
        item_schema = field_schema.get('item_schema')
        
        if not item_schema:
            # No item validation rules
            return value
        
        # Validate each item in the list
        validated_items = []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                logger.warning(f"{instrument}: '{field_name}[{i}]' is not a dict, skipping")
                continue
            
            # Validate this item as a nested config
            self._validate_config_fields(item, item_schema)
            validated_items.append(item)
        
        return validated_items