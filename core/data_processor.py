# core/data_processor.py
"""
Data processing module for particle sizing data.
"""

import pandas as pd
import numpy as np
import logging
from typing import Tuple, List, Optional
from config.constants import SIZE_COLUMN_NAMES, FREQUENCY_COLUMN_NAMES, RANDOM_DATA_BOUNDS

logger = logging.getLogger(__name__)

class ParticleDataProcessor:
    """Handles loading and processing of particle sizing data."""
    
    def __init__(self):
        self.data = None
        self.size_column = None
        self.frequency_column = None
    
    def load_csv(self, file_path: str) -> bool:
        """
        Load CSV file and attempt to identify size and frequency columns.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            bool: True if successfully loaded, False otherwise
        """
        try:
            self.data = pd.read_csv(file_path)
            logger.info(f"Loaded CSV with {len(self.data)} rows and {len(self.data.columns)} columns")
            
            # Auto-detect columns
            self._detect_columns()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            return False
    
    def _detect_columns(self):
        """Attempt to automatically detect size and frequency columns."""
        if self.data is None:
            return
        
        columns = self.data.columns.tolist()
        
        # Find size column
        for col in columns:
            if any(size_name.lower() in col.lower() for size_name in SIZE_COLUMN_NAMES):
                self.size_column = col
                break
        
        # Find frequency column
        for col in columns:
            if any(freq_name.lower() in col.lower() for freq_name in FREQUENCY_COLUMN_NAMES):
                self.frequency_column = col
                break
        
        logger.info(f"Detected columns - Size: {self.size_column}, Frequency: {self.frequency_column}")
    
    def get_columns(self) -> List[str]:
        """Get list of available columns."""
        if self.data is None:
            return []
        return self.data.columns.tolist()
    
    def set_columns(self, size_col: str, frequency_col: str):
        """Manually set the size and frequency columns."""
        if self.data is None:
            return
        
        if size_col in self.data.columns:
            self.size_column = size_col
        if frequency_col in self.data.columns:
            self.frequency_column = frequency_col
    
    def get_size_data(self) -> Optional[np.ndarray]:
        """Get the size data as numpy array."""
        if self.data is None or self.size_column is None:
            return None
        
        try:
            return self.data[self.size_column].dropna().values
        except Exception as e:
            logger.error(f"Error getting size data: {e}")
            return None
    
    def get_frequency_data(self) -> Optional[np.ndarray]:
        """Get the frequency data as numpy array."""
        if self.data is None or self.frequency_column is None:
            return None
        
        try:
            return self.data[self.frequency_column].dropna().values
        except Exception as e:
            logger.error(f"Error getting frequency data: {e}")
            return None
    
    def get_data_stats(self) -> dict:
        """Get basic statistics about the loaded data."""
        if self.data is None:
            return {}
        
        stats = {
            'total_rows': len(self.data),
            'total_columns': len(self.data.columns)
        }
        
        if self.size_column:
            size_data = self.get_size_data()
            if size_data is not None:
                stats['size_min'] = np.min(size_data)
                stats['size_max'] = np.max(size_data)
                stats['size_mean'] = np.mean(size_data)
        
        return stats
    
    def generate_random_data(self, n: int = None, distribution: str = 'lognormal') -> bool:
        """
        Generate random particle size data for testing purposes.
        
        Args:
            n: Number of data points to generate (uses default if None)
            distribution: Type of distribution ('lognormal', 'normal', 'uniform')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if n is None:
                n = RANDOM_DATA_BOUNDS['default_n']
            
            logger.info(f"Generating {n} random data points with {distribution} distribution")
            
            # Generate size data based on distribution type
            if distribution == 'lognormal':
                # Log-normal distribution is common for particle sizes
                mu, sigma = 2.0, 0.8  # Parameters for log-normal
                size_data = np.random.lognormal(mu, sigma, n)
                # Scale to desired range
                size_data = self._scale_to_range(size_data, 
                                               RANDOM_DATA_BOUNDS['size_min'], 
                                               RANDOM_DATA_BOUNDS['size_max'])
            
            elif distribution == 'normal':
                # Normal distribution
                mean = (RANDOM_DATA_BOUNDS['size_max'] + RANDOM_DATA_BOUNDS['size_min']) / 2
                std = (RANDOM_DATA_BOUNDS['size_max'] - RANDOM_DATA_BOUNDS['size_min']) / 6
                size_data = np.random.normal(mean, std, n)
                # Clip to bounds
                size_data = np.clip(size_data, RANDOM_DATA_BOUNDS['size_min'], 
                                  RANDOM_DATA_BOUNDS['size_max'])
            
            else:  # uniform
                size_data = np.random.uniform(RANDOM_DATA_BOUNDS['size_min'], 
                                            RANDOM_DATA_BOUNDS['size_max'], n)
            
            # Generate frequency data (using Poisson-like distribution)
            # Smaller particles tend to have higher frequencies
            relative_sizes = (size_data - np.min(size_data)) / (np.max(size_data) - np.min(size_data))
            # Invert so smaller particles have higher base frequency
            base_freq = RANDOM_DATA_BOUNDS['freq_max'] * (1 - relative_sizes * 0.7)
            # Add some randomness
            frequency_data = np.random.poisson(base_freq * 0.1) + np.random.randint(
                RANDOM_DATA_BOUNDS['freq_min'], 
                int(RANDOM_DATA_BOUNDS['freq_max'] * 0.1), 
                n
            )
            
            # Create DataFrame
            self.data = pd.DataFrame({
                'particle_size': size_data,
                'frequency': frequency_data
            })
            
            # Set columns
            self.size_column = 'particle_size'
            self.frequency_column = 'frequency'
            
            logger.info("Random data generated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate random data: {e}")
            return False
    
    def _scale_to_range(self, data: np.ndarray, min_val: float, max_val: float) -> np.ndarray:
        """Scale data to specified range while preserving distribution shape."""
        data_min, data_max = np.min(data), np.max(data)
        if data_max == data_min:
            return np.full(len(data), (min_val + max_val) / 2)
        
        # Scale to 0-1 first, then to desired range
        normalized = (data - data_min) / (data_max - data_min)
        return normalized * (max_val - min_val) + min_val