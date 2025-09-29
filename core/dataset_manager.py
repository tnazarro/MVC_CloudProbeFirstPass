"""
Dataset manager for handling multiple particle analysis datasets with instrument type support. Focused on handling the list of active datasets, their metadata, and analysis settings.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from core.data_processor import ParticleDataProcessor
from config.config_manager import ConfigManager


logger = logging.getLogger(__name__)

class DatasetManager:
    """Manages multiple particle analysis datasets."""
    
    def __init__(self):
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.active_dataset_id: Optional[str] = None
        self._color_palette = [
            '#FF6B6B',  # Red
            '#4ECDC4',  # Teal  
            '#45B7D1',  # Blue
            '#96CEB4',  # Green
            '#FFEAA7',  # Yellow
            '#DDA0DD',  # Plum
            '#98D8C8',  # Mint
            '#F7DC6F',  # Light Yellow
            '#BB8FCE',  # Light Purple
            '#85C1E9'   # Light Blue
        ]
        self._next_color_index = 0
        self.config_manager = ConfigManager()
    
    def add_dataset(self, 
                file_path: str, 
                tag: str = "",
                notes: str = "",
                skip_rows: int = 0) -> Optional[str]:
        """
        Add a new dataset from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            tag: User-defined tag for the dataset
            notes: Additional metadata/notes
            skip_rows: Number of rows to skip when loading
            
        Returns:
            Dataset ID if successful, None if failed
        """
        try:
            # Create unique ID for this dataset
            dataset_id = str(uuid.uuid4())
            
            # Create data processor and load the file
            data_processor = ParticleDataProcessor()
            
            if not data_processor.load_csv(file_path, skip_rows):
                logger.error(f"Failed to load dataset from {file_path}")
                return None
            
            # Extract filename from path
            filename = file_path.split('/')[-1].split('\\')[-1]
            
            # Assign color
            color = self._get_next_color()
            
            # Get detected instrument type from the data processor
            instrument_type = data_processor.get_instrument_type()
            
            # Try to get config for this instrument
            instrument_config = self.config_manager.get_instrument_config(instrument_type)
            
            # Start with programmatic defaults
            bin_count = 50
            size_column = data_processor.size_column
            
            # Apply config defaults if available
            if instrument_config:
                calibration = instrument_config.get('calibration', {})
                if 'bins' in calibration:
                    bin_count = calibration['bins']
                    print(f"📊 Applied bin count from config: {bin_count}")
                
                variants = instrument_config.get('variants', [])
                if variants and 'pbpKey' in variants[0]:
                    config_size_column = variants[0]['pbpKey']
                    if config_size_column in data_processor.get_columns():
                        size_column = config_size_column
                        print(f"📊 Applied size column from config: {size_column}")
            
            # Create dataset entry (with config-applied settings)
            dataset_info = {
                'id': dataset_id,
                'filename': filename,
                'file_path': file_path,
                'tag': tag or filename,
                'notes': notes,
                'color': color,
                'data_processor': data_processor,
                'loaded_at': datetime.now(),
                'skip_rows': skip_rows,
                'instrument_type': instrument_type,
                'analysis_settings': {
                    'data_mode': 'raw_measurements',
                    'bin_count': bin_count,  # Now from config!
                    'size_column': size_column,
                    'frequency_column': data_processor.frequency_column,
                    'show_stats_lines': True,
                    'show_gaussian_fit': True
                }
            }
            
            # Add to collection
            self.datasets[dataset_id] = dataset_info
            
            # Set as active if it's the first dataset
            if self.active_dataset_id is None:
                self.active_dataset_id = dataset_id
            
            logger.info(f"Added dataset: {filename} with tag '{tag}' and instrument type '{instrument_type}' (ID: {dataset_id})")
            return dataset_id
            
        except Exception as e:
            logger.error(f"Error adding dataset from {file_path}: {e}")
            return None
    
    def update_dataset_instrument_type(self, dataset_id: str, new_instrument_type: str) -> bool:
        """
        Update the instrument type for a dataset.
        
        Args:
            dataset_id: ID of the dataset to update
            new_instrument_type: New instrument type string
            
        Returns:
            bool: True if successful, False if dataset not found
        """
        if dataset_id in self.datasets:
            self.datasets[dataset_id]['data_processor'].set_instrument_type(new_instrument_type)
            logger.info(f"Updated instrument type for dataset {dataset_id} to '{new_instrument_type}'")
            return True
        return False
    
    def get_dataset_instrument_type(self, dataset_id: str) -> Optional[str]:
        """
        Get the instrument type for a specific dataset.
        """
        if dataset_id in self.datasets:
            return self.datasets[dataset_id]['data_processor'].get_instrument_type()
        return None
    
    def remove_dataset(self, dataset_id: str) -> bool:
        """Remove a dataset from the collection."""
        if dataset_id not in self.datasets:
            return False
        
        # If removing the active dataset, switch to another one
        if self.active_dataset_id == dataset_id:
            remaining_ids = [id for id in self.datasets.keys() if id != dataset_id]
            self.active_dataset_id = remaining_ids[0] if remaining_ids else None
        
        del self.datasets[dataset_id]
        logger.info(f"Removed dataset {dataset_id}")
        return True
    
    def set_active_dataset(self, dataset_id: str) -> bool:
        """Set the active dataset for analysis."""
        if dataset_id in self.datasets:
            self.active_dataset_id = dataset_id
            logger.info(f"Set active dataset to {dataset_id}")
            return True
        return False
    
    def get_active_dataset(self) -> Optional[Dict[str, Any]]:
        """Get the currently active dataset."""
        if self.active_dataset_id and self.active_dataset_id in self.datasets:
            return self.datasets[self.active_dataset_id]
        return None
    
    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific dataset by ID."""
        return self.datasets.get(dataset_id)
    
    def get_all_datasets(self) -> List[Dict[str, Any]]:
        """Get all datasets as a list, ordered by load time."""
        return sorted(self.datasets.values(), key=lambda x: x['loaded_at'])
    
    def get_dataset_ids(self) -> List[str]:
        """Get all dataset IDs, ordered by load time."""
        sorted_datasets = self.get_all_datasets()
        return [dataset['id'] for dataset in sorted_datasets]
    
    def update_dataset_tag(self, dataset_id: str, new_tag: str) -> bool:
        """Update the tag for a dataset."""
        if dataset_id in self.datasets:
            self.datasets[dataset_id]['tag'] = new_tag
            logger.info(f"Updated tag for dataset {dataset_id} to '{new_tag}'")
            return True
        return False
    
    def update_dataset_notes(self, dataset_id: str, new_notes: str) -> bool:
        """Update the notes for a dataset."""
        if dataset_id in self.datasets:
            self.datasets[dataset_id]['notes'] = new_notes
            logger.info(f"Updated notes for dataset {dataset_id}")
            return True
        return False
    
    def update_analysis_settings(self, dataset_id: str, settings: Dict[str, Any]) -> bool:
        """Update analysis settings for a specific dataset."""
        if dataset_id in self.datasets:
            self.datasets[dataset_id]['analysis_settings'].update(settings)
            return True
        return False
    
    def get_next_dataset_id(self) -> Optional[str]:
        """Get the ID of the next dataset for navigation."""
        if not self.active_dataset_id:
            return None
        
        ids = self.get_dataset_ids()
        try:
            current_index = ids.index(self.active_dataset_id)
            next_index = (current_index + 1) % len(ids)
            return ids[next_index]
        except ValueError:
            return None
    
    def get_previous_dataset_id(self) -> Optional[str]:
        """Get the ID of the previous dataset for navigation."""
        if not self.active_dataset_id:
            return None
        
        ids = self.get_dataset_ids()
        try:
            current_index = ids.index(self.active_dataset_id)
            previous_index = (current_index - 1) % len(ids)
            return ids[previous_index]
        except ValueError:
            return None
    
    def has_datasets(self) -> bool:
        """Check if any datasets are loaded."""
        return len(self.datasets) > 0
    
    def get_dataset_count(self) -> int:
        """Get the number of loaded datasets."""
        return len(self.datasets)
    
    def _get_next_color(self) -> str:
        """Get the next color from the palette."""
        color = self._color_palette[self._next_color_index]
        self._next_color_index = (self._next_color_index + 1) % len(self._color_palette)
        return color
    
    def clear_all_datasets(self) -> None:
        """Remove all datasets."""
        self.datasets.clear()
        self.active_dataset_id = None
        self._next_color_index = 0
        logger.info("Cleared all datasets")

    def get_dataset_order_by_id(self) -> List[str]:
        """Get dataset IDs in their current order."""
        return list(self.datasets.keys())

    def get_all_datasets_ordered(self) -> List[Dict[str, Any]]:
        """Get all datasets in the order they appear in the internal dictionary."""
        return list(self.datasets.values())