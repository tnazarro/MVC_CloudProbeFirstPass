"""
Data processing module for particle sizing data.
"""

import pandas as pd
import numpy as np
import logging
from typing import Tuple, List, Optional
from config.constants import SIZE_COLUMN_NAMES, FREQUENCY_COLUMN_NAMES, RANDOM_DATA_BOUNDS, SUPPORTED_CSV_ENCODINGS

logger = logging.getLogger(__name__)

class ParticleDataProcessor:
    """Handles loading and processing of particle sizing data."""
    
    def __init__(self):
        self.data = None
        self.size_column = None
        self.frequency_column = None
        self.data_mode = "raw_measurements"  # "pre_aggregated" or "raw_measurements"
        self.instrument_type = "Unknown"  # NEW: Store detected instrument type
    
    def detect_instrument_type(self, file_path: str, max_lines: int = 15) -> str:
        """
        Detect instrument type from CSV file by looking for "Instrument Type =" line.
        
        Args:
            file_path: Path to the CSV file
            max_lines: Maximum number of lines to search through
            
        Returns:
            str: Detected instrument type or "Unknown" if not found
        """
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        if line_num >= max_lines:
                            break
                        
                        # Look for "Instrument Type=" (case-insensitive)
                        line_clean = line.strip()
                        if "instrument type=" in line_clean.lower():
                            # Extract the part after "Instrument Type="
                            parts = line_clean.split('=', 1)
                            if len(parts) > 1:
                                instrument_type = parts[1].strip()
                                # Remove any quotes or extra whitespace
                                instrument_type = instrument_type.strip('"\'')
                                
                                if instrument_type:
                                    logger.info(f"Detected instrument type: {instrument_type}")
                                    self.instrument_type = instrument_type
                                    return instrument_type
                
                # If we get here, we successfully read the file but didn't find the instrument type
                logger.info(f"Instrument type not found in first {max_lines} lines of file")
                self.instrument_type = "Unknown"
                return "Unknown"
                
            except UnicodeDecodeError:
                # Try next encoding
                continue
            except Exception as e:
                logger.warning(f"Error detecting instrument type with encoding {encoding}: {e}")
                continue
        
        # If all encodings failed
        logger.warning(f"Failed to detect instrument type with any supported encoding")
        self.instrument_type = "Unknown"
        return "Unknown"

    
    def get_instrument_type(self) -> str:
        """
        Get the detected or set instrument type.
        """
        return self.instrument_type
    
    def set_instrument_type(self, instrument_type: str) -> None:
        """
        Manually set the instrument type (for future editability).
        """
        self.instrument_type = instrument_type.strip()
        logger.info(f"Instrument type manually set to: {self.instrument_type}")
    
    def load_csv(self, file_path: str, skip_rows: int = 0) -> bool:
        """
        Load CSV file and attempt to identify size and frequency columns.
        Also detects instrument type from the file.
        
        Args:
            file_path: Path to the CSV file
            skip_rows: Number of rows to skip from the beginning of the file
            
        Returns:
            bool: True if successfully loaded, False otherwise
        """
        # First, detect instrument type before loading the data
        self.detect_instrument_type(file_path)
        
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                # Load CSV with row skipping and encoding
                if skip_rows > 0:
                    self.data = pd.read_csv(file_path, skiprows=skip_rows, encoding=encoding)
                    logger.info(f"Loaded CSV with {skip_rows} rows skipped - {len(self.data)} rows and {len(self.data.columns)} columns remaining (encoding: {encoding})")
                else:
                    self.data = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"Loaded CSV with {len(self.data)} rows and {len(self.data.columns)} columns (encoding: {encoding})")
                
                # Auto-detect columns
                self._detect_columns()
                
                return True
                
            except UnicodeDecodeError:
                # Try next encoding
                continue
            except Exception as e:
                logger.error(f"Failed to load CSV with encoding {encoding}: {e}")
                continue
        
        # If all encodings failed
        logger.error(f"Failed to load CSV with any supported encoding. Tried: {', '.join(SUPPORTED_CSV_ENCODINGS)}")
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
    
    def set_data_mode(self, mode: str):
        """
        Set the data processing mode.
        
        Args:
            mode: Either "pre_aggregated" or "raw_measurements"
        """
        if mode in ["pre_aggregated", "raw_measurements"]:
            self.data_mode = mode
            logger.info(f"Data mode set to: {mode}")
            
            # Reset frequency column if switching to raw measurements
            if mode == "raw_measurements":
                self.frequency_column = None
        else:
            logger.warning(f"Invalid data mode: {mode}")
    
    def get_data_mode(self) -> str:
        """Get the current data processing mode."""
        return self.data_mode
    
    def set_columns(self, size_col: str, frequency_col: str = None):
        """
        Manually set the size and frequency columns.
        
        Args:
            size_col: Name of the size column
            frequency_col: Name of the frequency column (optional for raw measurements)
        """
        if self.data is None:
            return
        
        if size_col in self.data.columns:
            self.size_column = size_col
            
        # Only set frequency column in pre-aggregated mode
        if self.data_mode == "pre_aggregated" and frequency_col and frequency_col in self.data.columns:
            self.frequency_column = frequency_col
        elif self.data_mode == "raw_measurements":
            self.frequency_column = None
    
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
        # Return None for raw measurements mode (frequencies will be calculated during plotting)
        if self.data_mode == "raw_measurements":
            return None
            
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
            'total_columns': len(self.data.columns),
            'data_mode': self.data_mode,
            'instrument_type': self.instrument_type 
        }
        
        if self.size_column:
            size_data = self.get_size_data()
            if size_data is not None:
                stats['size_min'] = np.min(size_data)
                stats['size_max'] = np.max(size_data)
                stats['size_mean'] = np.mean(size_data)
                
                # Add mode-specific stats
                if self.data_mode == "raw_measurements":
                    stats['unique_measurements'] = len(np.unique(size_data))
                    stats['total_measurements'] = len(size_data)
                elif self.data_mode == "pre_aggregated":
                    if self.frequency_column:
                        freq_data = self.get_frequency_data()
                        if freq_data is not None:
                            stats['total_frequency'] = np.sum(freq_data)
                            stats['frequency_mean'] = np.mean(freq_data)
        
        return stats
    
    def preview_csv(self, file_path: str, preview_rows: int = 10) -> dict:
        """
        Preview the first few rows of a CSV file to help identify junk data.
        Now also detects and includes instrument type information.
        
        Args:
            file_path: Path to the CSV file
            preview_rows: Number of rows to preview
            
        Returns:
            dict: Contains preview data, total rows, columns info, and instrument type
        """
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                # First detect instrument type
                detected_instrument = self.detect_instrument_type(file_path)
                
                # Read just the preview rows
                with open(file_path, 'r', encoding=encoding) as f:
                    preview_lines = [f.readline().strip() for _ in range(preview_rows)]
                
                # Get total line count with same encoding
                with open(file_path, 'r', encoding=encoding) as f:
                    total_lines = sum(1 for _ in f)
                
                # Try to parse the file normally to get column info
                try:
                    sample_df = pd.read_csv(file_path, nrows=5, encoding=encoding)
                    columns = sample_df.columns.tolist()
                    detected_columns = len(columns)
                except:
                    columns = []
                    detected_columns = 0
                
                return {
                    'success': True,
                    'preview_lines': preview_lines,
                    'total_lines': total_lines,
                    'detected_columns': detected_columns,
                    'column_names': columns,
                    'encoding_used': encoding,
                    'instrument_type': detected_instrument
                }
                
            except UnicodeDecodeError:
                # Try next encoding
                continue
            except Exception as e:
                logger.error(f"Failed to preview CSV with encoding {encoding}: {e}")
                continue
        
        # If all encodings failed
        return {
            'success': False,
            'error': f"Could not read file with any supported encoding. Tried: {', '.join(SUPPORTED_CSV_ENCODINGS)}",
            'instrument_type': "Unknown"
        }
    
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
            
            # Set instrument type for generated data
            self.instrument_type = "Generated Data"
            
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