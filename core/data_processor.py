"""
Data processing module for particle sizing data.
"""

import pandas as pd
import numpy as np
import logging
import os
import re
from typing import Tuple, List, Optional, Dict, Any
from config.constants import SIZE_COLUMN_NAMES, FREQUENCY_COLUMN_NAMES, RANDOM_DATA_BOUNDS, SUPPORTED_CSV_ENCODINGS

logger = logging.getLogger(__name__)

# Supported instruments from requirements document
#Not sure if it's better here, or in constants.py
SUPPORTED_INSTRUMENTS = {
    'CDP', 'FM-100', 'FM 100', 'FM-120', 'FM 120', 'CAS', 'CAS-DPOL', 'CAS DPOL' 
    'BCPD', 'BCP', 'GFAS'
}

# Filename prefix to instrument name mapping
FILENAME_PREFIX_MAP = {
    'CDP': 'CDP',
    'FM': 'FM-120',
    'FOG': 'FM-120',
    'CAS': 'CAS',
    'BCPD': 'BCPD',
    'BCP': 'BCP',
    'GFAS': 'GFAS'
}

class ParticleDataProcessor:
    """Handles loading and processing of particle sizing data."""
    
    def __init__(self):
        self.data = None
        self.size_column = None
        self.frequency_column = None
        self.data_mode = "raw_measurements"  # "pre_aggregated" or "raw_measurements"
        self.instrument_info = {
            'name': 'Unknown',
            'version': None,
            'pads_version': None,
            'detection_method': None,
            'file_format': None,  # NEW: 'hk' or 'pbp'
            'calibration': {
                'has_calibration': False,
                'sizes': None,
                'thresholds': None,
                'bin_count': 0,
                'order': None
            }
        }
    
    def detect_instrument_type(self, file_path: str, max_lines: int = 60) -> dict:
        """
        Detect instrument type using multiple strategies:
        1. Look for "Instrument Type=" pattern (most declarative)
        2. Look for "<instrument> version =" pattern (PADS format)
        3. Extract from filename as fallback
        
        Scans all lines up to max_lines to collect name, version, and PADS version.
        
        Args:
            file_path: Path to the CSV file
            max_lines: Maximum number of lines to search through (default 60 to catch CDP metadata)
            
        Returns:
            dict: Instrument information with keys:
                - name: Instrument name (e.g., "CAS DPOL")
                - version: Instrument version if found (e.g., "4.03.06")
                - pads_version: PADS version if found
                - detection_method: How instrument was detected
        """
        
        result = {
            'name': 'Unknown',
            'version': None,
            'pads_version': None,
            'detection_method': None
        }
        
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    lines = [f.readline() for _ in range(max_lines)]
                
                # Scan all lines to collect all available information
                for line_num, line in enumerate(lines):
                    line_clean = line.strip()
                    line_lower = line_clean.lower()
                    
                    # Check for PADS version (always capture this)
                    if "pads version" in line_lower and "=" in line_clean:
                        parts = line_clean.split('=', 1)
                        if len(parts) > 1:
                            result['pads_version'] = parts[1].strip()
                        continue
                    
                    # Strategy 1: Look for "Instrument Type=" (most declarative)
                    if "instrument type=" in line_lower and result['name'] == 'Unknown':
                        parts = line_clean.split('=', 1)
                        if len(parts) > 1:
                            instrument_name = parts[1].strip().strip('"\'')
                            if instrument_name:
                                result['name'] = instrument_name
                                result['detection_method'] = 'explicit_declaration'
                                logger.info(f"Detected instrument type (explicit): {instrument_name}")
                    
                    # Strategy 2: Look for "<instrument> version =" pattern
                    elif "version" in line_lower and "=" in line_clean and result['name'] == 'Unknown':
                        version_index = line_lower.find("version")
                        potential_name = line_clean[:version_index].strip()
                        
                        # Validate it's a known instrument (case-insensitive match)
                        name_upper = potential_name.upper()
                        for supported in SUPPORTED_INSTRUMENTS:
                            supported_upper = supported.upper()
                            # Check if the supported instrument name is in the potential name
                            # This handles cases like "CDP PBP version" or "BCPD Beta version"
                            if supported_upper in name_upper:
                                # Extract version number
                                parts = line_clean.split('=', 1)
                                if len(parts) > 1:
                                    version = parts[1].strip()
                                    # Use the canonical name from SUPPORTED_INSTRUMENTS
                                    result['name'] = supported
                                    result['version'] = version
                                    result['detection_method'] = 'version_pattern'
                                    logger.info(f"Detected instrument type (version pattern): {supported} v{version}")
                                    break
                
                # After scanning all lines, if we found something, return it
                if result['name'] != 'Unknown':
                    self.instrument_info = result
                    return result
                
                # Strategy 3: Parse from filename as fallback
                filename_upper = os.path.basename(file_path).upper()
                
                for prefix, instrument_name in FILENAME_PREFIX_MAP.items():
                    if filename_upper.startswith(prefix.upper()):
                        result['name'] = instrument_name
                        result['detection_method'] = 'filename_pattern'
                        logger.info(f"Detected instrument type (filename): {instrument_name}")
                        self.instrument_info = result
                        return result
                
                logger.info(f"Instrument type not found in first {max_lines} lines or filename")
                self.instrument_info = result
                return result
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error detecting instrument type with encoding {encoding}: {e}")
                continue
        
        logger.warning("Failed to detect instrument type with any supported encoding")
        self.instrument_info = result
        return result

    def _parse_calibration_data(self, file_path: str, max_lines: int = 100) -> dict:
        """
        Parse calibration data (Sizes and Thresholds) from file header.
        Auto-detects order since some instruments have reversed order.
        
        Args:
            file_path: Path to the CSV file
            max_lines: Maximum number of header lines to search
            
        Returns:
            dict: Calibration information with keys:
                - has_calibration: bool
                - sizes: list of floats (particle sizes in µm)
                - thresholds: list of ints (ADC threshold values)
                - bin_count: int (number of bins)
                - order: str ('sizes_first' or 'thresholds_first')
        """
        result = {
            'has_calibration': False,
            'sizes': None,
            'thresholds': None,
            'bin_count': 0,
            'order': None
        }
        
        sizes_line = None
        thresholds_line = None
        sizes_line_num = None
        thresholds_line_num = None
        
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        if line_num >= max_lines:
                            break
                        
                        line_clean = line.strip()
                        line_lower = line_clean.lower()
                        
                        # Look for Sizes pattern: Sizes=<N>value1,value2,...
                        if line_lower.startswith('sizes='):
                            sizes_line = line_clean
                            sizes_line_num = line_num
                        
                        # Look for Thresholds pattern: Thresholds=<N>value1,value2,...
                        elif line_lower.startswith('thresholds='):
                            thresholds_line = line_clean
                            thresholds_line_num = line_num
                        
                        # Stop scanning after data separator
                        if line_clean.startswith('****'):
                            break
                
                # Process if both found
                if sizes_line and thresholds_line:
                    sizes_array = self._parse_calibration_array(sizes_line, 'Sizes')
                    thresholds_array = self._parse_calibration_array(thresholds_line, 'Thresholds')
                    
                    if sizes_array and thresholds_array:
                        # Validate arrays have same length
                        if len(sizes_array) != len(thresholds_array):
                            logger.warning(
                                f"Calibration data length mismatch: "
                                f"Sizes={len(sizes_array)}, Thresholds={len(thresholds_array)}"
                            )
                            return result
                        
                        # Determine order
                        if sizes_line_num < thresholds_line_num:
                            order = 'sizes_first'
                        else:
                            order = 'thresholds_first'
                        
                        result = {
                            'has_calibration': True,
                            'sizes': sizes_array,
                            'thresholds': thresholds_array,
                            'bin_count': len(sizes_array),
                            'order': order
                        }
                        
                        logger.info(
                            f"Parsed calibration data: {len(sizes_array)} bins, "
                            f"order={order}, size range={sizes_array[0]}-{sizes_array[-1]} µm"
                        )
                        
                        return result
                
                # If we got here with this encoding, parsing is done (even if no calibration found)
                return result
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error parsing calibration data with encoding {encoding}: {e}")
                continue
        
        logger.warning("Failed to parse calibration data with any supported encoding")
        return result
    
    def _parse_calibration_array(self, line: str, field_name: str) -> Optional[List]:
        """
        Parse a calibration array line like: Sizes=<30>3,4,5,6,...
        
        Args:
            line: The line containing the array
            field_name: Name of field for logging (e.g., 'Sizes')
            
        Returns:
            List of parsed values (floats for Sizes, ints for Thresholds) or None if parsing fails
        """
        try:
            # Split on '=' to get the value part
            parts = line.split('=', 1)
            if len(parts) != 2:
                return None
            
            value_part = parts[1].strip()
            
            # Extract count from <N> if present
            if value_part.startswith('<'):
                # Format: <30>3,4,5,6,...
                bracket_end = value_part.find('>')
                if bracket_end == -1:
                    logger.warning(f"Invalid {field_name} format: missing '>'")
                    return None
                
                count_str = value_part[1:bracket_end]
                values_str = value_part[bracket_end + 1:]
                
                try:
                    expected_count = int(count_str)
                except ValueError:
                    logger.warning(f"Invalid {field_name} count: {count_str}")
                    return None
            else:
                # Format without <N>: just comma-separated values
                values_str = value_part
                expected_count = None
            
            # Parse comma-separated values
            value_strings = values_str.split(',')
            
            # Determine if we're parsing floats (Sizes) or ints (Thresholds)
            is_sizes = (field_name.lower() == 'sizes')
            
            parsed_values = []
            for v_str in value_strings:
                v_str = v_str.strip()
                if not v_str:
                    continue
                
                try:
                    if is_sizes:
                        parsed_values.append(float(v_str))
                    else:
                        parsed_values.append(int(v_str))
                except ValueError:
                    logger.warning(f"Invalid {field_name} value: {v_str}")
                    return None
            
            # Validate count if specified
            if expected_count is not None and len(parsed_values) != expected_count:
                logger.warning(
                    f"{field_name} count mismatch: expected {expected_count}, got {len(parsed_values)}"
                )
                return None
            
            return parsed_values
            
        except Exception as e:
            logger.error(f"Error parsing {field_name} array: {e}")
            return None

    def _detect_bin_columns(self, column_names: List[str], expected_bin_count: int) -> Optional[List[str]]:
        """
        Detect bin columns in HK (pre-aggregated) files.
        
        Looks for patterns like: "Bin 1", "CDP Bin 1", "Fog Monitor Bin 1", etc.
        
        Args:
            column_names: List of column names from CSV
            expected_bin_count: Expected number of bins from calibration
            
        Returns:
            Ordered list of bin column names, or None if detection fails
        """
        
        # Pattern to match bin columns: anything ending with "Bin <number>"
        # Examples: "Bin 1", "CDP Bin 1", "Fog Monitor Bin 1"
        bin_pattern = re.compile(r'^(.*)Bin\s+(\d+)$', re.IGNORECASE)
        
        bin_columns = {}  # {bin_number: column_name}
        
        for col in column_names:
            match = bin_pattern.match(col.strip())
            if match:
                prefix = match.group(1).strip()
                bin_num = int(match.group(2))
                bin_columns[bin_num] = col
        
        # Validate we found bins
        if not bin_columns:
            logger.debug("No bin columns detected")
            return None
        
        # Check if we have the expected number of bins
        if len(bin_columns) != expected_bin_count:
            logger.warning(
                f"Bin count mismatch: found {len(bin_columns)} bin columns, "
                f"expected {expected_bin_count} from calibration"
            )
            return None
        
        # Validate bins are sequential (1, 2, 3, ... N)
        bin_numbers = sorted(bin_columns.keys())
        expected_sequence = list(range(1, expected_bin_count + 1))
        
        if bin_numbers != expected_sequence:
            logger.error(
                f"Bin columns are not sequential. Found: {bin_numbers}, "
                f"Expected: {expected_sequence}"
            )
            return None
        
        # Return columns in order
        ordered_columns = [bin_columns[i] for i in expected_sequence]
        
        logger.info(
            f"Detected {len(ordered_columns)} bin columns: "
            f"{ordered_columns[0]} ... {ordered_columns[-1]}"
        )
        
        return ordered_columns

    def _detect_file_format(self, metadata: Dict[str, Any]) -> str:
        """
        Detect if file is HK (pre-aggregated) or PBP (particle-by-particle).
        
        Detection strategy:
        1. Check for bin columns matching calibration bin_count → HK
        2. Check for "Size [counts]" or similar column → PBP
        3. Default to PBP if ambiguous
        
        Args:
            metadata: Metadata dict from _parse_csv_metadata
            
        Returns:
            'hk' or 'pbp'
        """
        columns = metadata.get('sample_columns', [])
        calibration = self.instrument_info.get('calibration', {})
        
        # Only attempt detection if we have calibration data
        if not calibration.get('has_calibration', False):
            logger.info("No calibration data, defaulting to PBP format")
            return 'pbp'
        
        bin_count = calibration['bin_count']
        
        # Strategy 1: Look for bin columns
        bin_columns = self._detect_bin_columns(columns, bin_count)
        if bin_columns and len(bin_columns) == bin_count:
            logger.info(f"Detected HK format: found {bin_count} bin columns")
            return 'hk'
        
        # Strategy 2: Look for PBP size column
        for col in columns:
            col_lower = col.lower()
            # Look for patterns like "Size [counts]", "Size(counts)", etc.
            if 'size' in col_lower and ('count' in col_lower or '[' in col_lower):
                logger.info(f"Detected PBP format: found size column '{col}'")
                return 'pbp'
        
        # Default to PBP
        logger.warning("Could not definitively detect file format, defaulting to PBP")
        return 'pbp'

    def _load_hk_data(self, file_path: str, metadata: Dict[str, Any], skip_rows: int = 0) -> bool:
        """
        Load pre-aggregated HK (housekeeping) file data.
        
        HK files have bin columns with counts already aggregated by the instrument.
        We extract the calibration sizes and sum bin counts across all time periods.
        
        Args:
            file_path: Path to CSV file
            metadata: Metadata from _parse_csv_metadata
            skip_rows: Number of rows to skip
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            calibration = self.instrument_info['calibration']
            
            # Detect bin columns
            bin_columns = self._detect_bin_columns(
                metadata['sample_columns'], 
                calibration['bin_count']
            )
            
            if not bin_columns:
                logger.error("Failed to detect bin columns in HK file")
                return False
            
            # Load the full dataset
            encoding = metadata['encoding']
            df = pd.read_csv(file_path, skiprows=skip_rows, encoding=encoding)
            
            logger.info(f"Loaded HK file with {len(df)} rows (time periods)")
            
            # Extract bin data and sum across all rows
            bin_counts = []
            for bin_col in bin_columns:
                if bin_col not in df.columns:
                    logger.error(f"Bin column '{bin_col}' not found in dataframe")
                    return False
                
                # Sum all values in this bin column
                total_count = df[bin_col].sum()
                bin_counts.append(total_count)
            
            # Convert to numpy arrays
            sizes = np.array(calibration['sizes'])
            counts = np.array(bin_counts)
            
            logger.info(
                f"Aggregated HK data: {len(sizes)} bins, "
                f"total particles: {counts.sum():.0f}"
            )
            
            # Store as pre-aggregated data
            self.data = pd.DataFrame({
                'size': sizes,
                'frequency': counts
            })
            
            self.size_column = 'size'
            self.frequency_column = 'frequency'
            self.data_mode = 'pre_aggregated'
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading HK data: {e}")
            return False

    def map_counts_to_sizes(self, counts: np.ndarray, calibration_data: dict = None) -> np.ndarray:
        """
        Map ADC threshold counts to particle sizes using calibration data.
        
        Uses inclusive upper bound: count <= threshold[i] maps to size[i].
        
        Example:
            Thresholds: [91, 111, 159, ...]
            Sizes:      [3,  4,   5,   ...]
            Count 109:  > 91 and <= 111, maps to size 4 µm
        
        Args:
            counts: Array of ADC threshold count values
            calibration_data: Calibration dict (uses self.instrument_info['calibration'] if None)
            
        Returns:
            Array of particle sizes (in µm) corresponding to input counts
            
        Raises:
            ValueError: If no calibration data available
        """
        # Use provided calibration or fall back to instrument_info
        if calibration_data is None:
            calibration_data = self.instrument_info.get('calibration', {})
        
        # Validate calibration data exists
        if not calibration_data.get('has_calibration', False):
            raise ValueError("No calibration data available for count-to-size mapping")
        
        thresholds = np.array(calibration_data['thresholds'])
        sizes = np.array(calibration_data['sizes'])
        
        # Validate input
        if len(thresholds) != len(sizes):
            raise ValueError(
                f"Calibration data mismatch: {len(thresholds)} thresholds, {len(sizes)} sizes"
            )
        
        # Convert counts to numpy array if needed
        counts = np.asarray(counts)
        
        # Initialize output array with NaN (for invalid/out-of-range values)
        mapped_sizes = np.full(counts.shape, np.nan)
        
        # Use numpy's searchsorted for efficient bin assignment
        # searchsorted finds indices where counts would be inserted to maintain order
        # Using 'right' side means count <= threshold[i]
        bin_indices = np.searchsorted(thresholds, counts, side='right')
        
        # Handle edge cases:
        # - bin_indices == 0: count is <= first threshold → assign to first bin
        # - bin_indices > len(sizes): count is > last threshold → out of range (keep as NaN)
        
        # Clip indices to valid range [0, len(sizes)-1]
        # Any count <= first threshold maps to first size (index 0)
        # Any count > last threshold will be clipped to len(sizes), but we'll handle separately
        valid_mask = bin_indices < len(sizes)
        
        # Assign sizes for valid bins
        mapped_sizes[valid_mask] = sizes[bin_indices[valid_mask]]
        
        # Log warnings for out-of-range values
        n_out_of_range = np.sum(~valid_mask)
        if n_out_of_range > 0:
            max_threshold = thresholds[-1]
            logger.warning(
                f"{n_out_of_range} count value(s) exceed maximum threshold "
                f"({max_threshold}). These will be excluded from analysis."
            )
        
        return mapped_sizes

    def get_instrument_type(self) -> str:
        """
        Get the detected or set instrument type.
        """
        return self.instrument_info['name']
    
    def get_instrument_info(self) -> dict:
        """
        Get the full instrument information dictionary.
        
        Returns:
            dict with keys: name, version, pads_version, detection_method
        """
        return self.instrument_info.copy()

    def set_instrument_type(self, instrument_type: str, version: str = None) -> None:
        """
        Manually set the instrument type and optionally version.
        
        Args:
            instrument_type: Instrument name
            version: Optional instrument version
        """
        self.instrument_info['name'] = instrument_type.strip()
        if version:
            self.instrument_info['version'] = version.strip()
        self.instrument_info['detection_method'] = 'manual'
        logger.info(f"Instrument type manually set to: {instrument_type}")

    def _parse_csv_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Parse CSV file metadata including encoding detection and basic file info.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Dict containing:
                - success: bool
                - encoding: str (if successful)
                - error: str (if failed)
                - total_lines: int (if successful)
                - sample_columns: list (if successful)
        """
        # First, detect instrument type
        detected_instrument = self.detect_instrument_type(file_path)
        
        # Parse calibration data (Sizes/Thresholds)
        calibration_data = self._parse_calibration_data(file_path)
        
        # Add calibration to instrument info
        detected_instrument['calibration'] = calibration_data

        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                # Get total line count
                with open(file_path, 'r', encoding=encoding) as f:
                    total_lines = sum(1 for _ in f)
                
                # Try to parse a small sample to get column info
                try:
                    sample_df = pd.read_csv(file_path, nrows=5, encoding=encoding)
                    sample_columns = sample_df.columns.tolist()
                except Exception:
                    sample_columns = []
                
                return {
                    'success': True,
                    'encoding': encoding,
                    'total_lines': total_lines,
                    'sample_columns': sample_columns,
                    'instrument_info': detected_instrument
                }
                
            except UnicodeDecodeError:
                # Try next encoding
                continue
            except Exception as e:
                logger.warning(f"Error parsing CSV metadata with encoding {encoding}: {e}")
                continue
        
        # If all encodings failed
        error_msg = f"Could not read file with any supported encoding. Tried: {', '.join(SUPPORTED_CSV_ENCODINGS)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'instrument_info': {'name': 'Unknown', 'version': None, 'pads_version': None, 'detection_method': None}
        }

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
        # Parse metadata (includes instrument type detection)
        metadata = self._parse_csv_metadata(file_path)
        
        if not metadata['success']:
            logger.error(f"Failed to parse CSV metadata: {metadata['error']}")
            return False
        
        # Use the detected encoding to load the full dataset
        encoding = metadata['encoding']

        # Detect file format (HK vs PBP)
        file_format = self._detect_file_format(metadata)
        self.instrument_info['file_format'] = file_format
        
        logger.info(f"File format detected: {file_format.upper()}")
        
        # Route to appropriate loader
        if file_format == 'hk':
            return self._load_hk_data(file_path, metadata, skip_rows)
        else:
            # For now, fall through to existing PBP loading logic
            logger.info("Loading as PBP format (existing logic)")
 

        try:
            # Load CSV with row skipping
            if skip_rows > 0:
                self.data = pd.read_csv(file_path, skiprows=skip_rows, encoding=encoding)
                logger.info(f"Loaded CSV with {skip_rows} rows skipped - {len(self.data)} rows and {len(self.data.columns)} columns remaining (encoding: {encoding})")
            else:
                self.data = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"Loaded CSV with {len(self.data)} rows and {len(self.data.columns)} columns (encoding: {encoding})")
            
            # Auto-detect columns
            self._detect_columns()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV with detected encoding {encoding}: {e}")
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
            'instrument_info': self.instrument_info
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
        Also detects and includes instrument type information.
        
        Args:
            file_path: Path to the CSV file
            preview_rows: Number of rows to preview
            
        Returns:
            dict: Contains preview data, total rows, columns info, and instrument type
        """
        # Use the common metadata parsing function
        metadata = self._parse_csv_metadata(file_path)
        
        if not metadata['success']:
            return {
                'success': False,
                'error': metadata['error'],
                'instrument_type': metadata.get('instrument_info', {}).get('name', 'Unknown')
            }
        
        # Use the detected encoding to read preview lines
        encoding = metadata['encoding']
        
        try:
            # Read just the preview rows
            with open(file_path, 'r', encoding=encoding) as f:
                preview_lines = [f.readline().strip() for _ in range(preview_rows)]
            
            return {
                'success': True,
                'preview_lines': preview_lines,
                'total_lines': metadata['total_lines'],
                'detected_columns': len(metadata['sample_columns']),
                'column_names': metadata['sample_columns'],
                'encoding_used': encoding,
                'instrument_type': metadata['instrument_info']['name']
            }
            
        except Exception as e:
            logger.error(f"Failed to read preview lines with encoding {encoding}: {e}")
            return {
                'success': False,
                'error': f"Failed to read preview lines: {str(e)}",
                'instrument_type': metadata.get('instrument_info', {}).get('name', 'Unknown')
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
            
            # Set instrument type for generated data (deprecated, but kept for compatibility)
            self.instrument_info = {
                'name': 'Generated Data',
                'version': None,
                'pads_version': None,
                'detection_method': 'generated'
            }
            
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