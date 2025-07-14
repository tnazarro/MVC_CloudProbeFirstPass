# config/config_manager.py
"""
Configuration manager for loading, saving, and managing application settings via JSON files.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigurationManager:
    """Manages application configuration through JSON files."""
    
    def __init__(self):
        self.config_data: Dict[str, Any] = {}
        self.config_file_path: Optional[str] = None
        self.default_config = self._get_default_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration structure."""
        return {
            "metadata": {
                "config_version": "1.0",
                "created_date": datetime.now().isoformat(),
                "description": "Particle Data Analyzer Configuration",
                "author": ""
            },
            "analysis_settings": {
                "default_bin_count": 50,
                "default_data_mode": "pre_aggregated",
                "default_analysis_mode": "calibration",
                "show_stats_lines": True,
                "auto_detect_columns": True
            },
            "ui_settings": {
                "window_geometry": "1400x900",
                "default_skip_rows": 0,
                "remember_last_directory": True,
                "last_directory": ""
            },
            "column_mappings": {
                "size_column_names": [
                    "size", "diameter", "particle_size", "Size", "Diameter",
                    "d", "D", "particle_diameter", "grain_size"
                ],
                "frequency_column_names": [
                    "frequency", "count", "number", "Frequency", "Count",
                    "freq", "n", "Number", "occurrences", "weight"
                ]
            },
            "plot_settings": {
                "default_width": 8,
                "default_height": 6,
                "default_dpi": 100,
                "color_palette": [
                    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
                    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9"
                ],
                "statistical_line_colors": {
                    "mean": "red",
                    "std_1": "orange", 
                    "std_2": "purple"
                }
            },
            "random_data_generation": {
                "size_bounds": {
                    "min": 0.1,
                    "max": 100.0
                },
                "frequency_bounds": {
                    "min": 1,
                    "max": 1000
                },
                "default_point_count": 500,
                "available_distributions": ["lognormal", "normal", "uniform"]
            },
            "file_processing": {
                "supported_encodings": ["utf-8", "windows-1252", "iso-8859-1", "cp1252", "latin1"],
                "preview_max_lines": 1000,
                "queue_processing_enabled": True
            },
            "report_settings": {
                "default_format": "pdf",
                "include_metadata": True,
                "include_dataset_notes": True,
                "include_analysis_params": True,
                "page_size": "A4"
            }
        }
    
    def load_config(self, file_path: str) -> bool:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the JSON configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            self.config_file_path = file_path
            
            # Validate the configuration
            if self._validate_config():
                logger.info(f"Configuration loaded successfully from {file_path}")
                return True
            else:
                logger.warning(f"Configuration file {file_path} has validation issues")
                return False
                
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {file_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration file {file_path}: {e}")
            return False
    
    def save_config(self, file_path: str, config_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save configuration to a JSON file.
        
        Args:
            file_path: Path where to save the configuration
            config_data: Optional config data to save (uses current if None)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data_to_save = config_data or self.config_data
            
            # Update metadata
            if "metadata" not in data_to_save:
                data_to_save["metadata"] = {}
            
            data_to_save["metadata"]["last_modified"] = datetime.now().isoformat()
            data_to_save["metadata"]["config_version"] = "1.0"
            
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            
            self.config_file_path = file_path
            logger.info(f"Configuration saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration to {file_path}: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """
        Validate the loaded configuration structure.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        if not isinstance(self.config_data, dict):
            logger.error("Configuration must be a JSON object")
            return False
        
        # Check for required top-level sections
        required_sections = ["analysis_settings", "ui_settings", "plot_settings"]
        missing_sections = [section for section in required_sections 
                          if section not in self.config_data]
        
        if missing_sections:
            logger.warning(f"Configuration missing sections: {missing_sections}")
            # We'll allow this but merge with defaults
        
        return True
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration, merged with defaults.
        
        Returns:
            Dict: Complete configuration with defaults filled in
        """
        if not self.config_data:
            return self.default_config.copy()
        
        # Deep merge with defaults
        merged_config = self._deep_merge(self.default_config.copy(), self.config_data)
        return merged_config
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with overlay taking precedence.
        
        Args:
            base: Base dictionary (defaults)
            overlay: Overlay dictionary (loaded config)
            
        Returns:
            Dict: Merged dictionary
        """
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a specific setting value.
        
        Args:
            section: Configuration section (e.g., 'analysis_settings')
            key: Setting key within the section
            default: Default value if not found
            
        Returns:
            Any: Setting value or default
        """
        config = self.get_config()
        return config.get(section, {}).get(key, default)
    
    def update_setting(self, section: str, key: str, value: Any) -> None:
        """
        Update a specific setting value.
        
        Args:
            section: Configuration section
            key: Setting key within the section
            value: New value to set
        """
        if section not in self.config_data:
            self.config_data[section] = {}
        
        self.config_data[section][key] = value
        logger.debug(f"Updated setting {section}.{key} = {value}")
    
    def export_current_settings(self, ui_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export current UI state as configuration.
        
        Args:
            ui_state: Current UI state from the application
            
        Returns:
            Dict: Configuration dictionary ready for saving
        """
        config = self.default_config.copy()
        
        # Update with current UI state
        if "analysis_settings" in ui_state:
            config["analysis_settings"].update(ui_state["analysis_settings"])
        
        if "ui_settings" in ui_state:
            config["ui_settings"].update(ui_state["ui_settings"])
        
        if "plot_settings" in ui_state:
            config["plot_settings"].update(ui_state["plot_settings"])
        
        # Add metadata
        config["metadata"]["created_date"] = datetime.now().isoformat()
        config["metadata"]["description"] = "Exported from Particle Data Analyzer"
        
        return config
    
    def get_column_mappings(self) -> Dict[str, list]:
        """Get column name mappings for auto-detection."""
        config = self.get_config()
        return config.get("column_mappings", {
            "size_column_names": ["size", "diameter", "particle_size", "Size", "Diameter"],
            "frequency_column_names": ["frequency", "count", "number", "Frequency", "Count"]
        })
    
    def get_ui_defaults(self) -> Dict[str, Any]:
        """Get default UI settings."""
        config = self.get_config()
        return config.get("ui_settings", {})
    
    def get_analysis_defaults(self) -> Dict[str, Any]:
        """Get default analysis settings."""
        config = self.get_config()
        return config.get("analysis_settings", {})
    
    def get_plot_defaults(self) -> Dict[str, Any]:
        """Get default plot settings."""
        config = self.get_config()
        return config.get("plot_settings", {})
    
    def has_config_loaded(self) -> bool:
        """Check if a configuration file has been loaded."""
        return bool(self.config_data and self.config_file_path)
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        Get information about the currently loaded configuration.
        
        Returns:
            Dict: Configuration metadata and file info
        """
        if not self.has_config_loaded():
            return {
                "loaded": False,
                "file_path": None,
                "metadata": {}
            }
        
        config = self.get_config()
        metadata = config.get("metadata", {})
        
        return {
            "loaded": True,
            "file_path": self.config_file_path,
            "metadata": metadata,
            "sections": list(config.keys()),
            "total_settings": sum(len(v) if isinstance(v, dict) else 1 for v in config.values())
        }
    
    def preview_config(self, file_path: str) -> Dict[str, Any]:
        """
        Preview a configuration file without loading it.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Dict: Preview information about the config file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Extract key information for preview
            metadata = config_data.get("metadata", {})
            sections = list(config_data.keys())
            
            preview_info = {
                "success": True,
                "file_path": file_path,
                "file_size": Path(file_path).stat().st_size,
                "metadata": metadata,
                "sections": sections,
                "section_count": len(sections),
                "is_valid": isinstance(config_data, dict),
                "sample_settings": {}
            }
            
            # Get sample settings from each section
            for section in sections[:5]:  # Limit to first 5 sections
                if isinstance(config_data[section], dict):
                    sample_keys = list(config_data[section].keys())[:3]  # First 3 keys
                    preview_info["sample_settings"][section] = {
                        key: config_data[section][key] for key in sample_keys
                    }
            
            return preview_info
            
        except FileNotFoundError:
            return {"success": False, "error": "File not found"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}
    
    def create_sample_config(self, file_path: str) -> bool:
        """
        Create a sample configuration file with all default settings.
        
        Args:
            file_path: Path where to save the sample config
            
        Returns:
            bool: True if successful, False otherwise
        """
        sample_config = self.default_config.copy()
        sample_config["metadata"]["description"] = "Sample Particle Data Analyzer Configuration"
        sample_config["metadata"]["author"] = "Generated by Particle Data Analyzer"
        
        return self.save_config(file_path, sample_config)