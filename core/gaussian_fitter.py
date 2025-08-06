"""
Gaussian curve fitting module for particle size distribution analysis.
"""

import numpy as np
import logging
from typing import Tuple, Optional, Dict, Any
from scipy.optimize import curve_fit
from scipy import stats

logger = logging.getLogger(__name__)

class GaussianFitter:
    """Handles Gaussian curve fitting for particle size distributions."""
    
    def __init__(self):
        self.last_fit_params = None
        self.last_fit_covariance = None
        self.last_fit_quality = None
        
    def fit_histogram_data(self, bin_centers: np.ndarray, bin_counts: np.ndarray, 
                          initial_guess: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
        """
        Fit a Gaussian curve to histogram data.
        
        Args:
            bin_centers: X-coordinates of histogram bin centers
            bin_counts: Y-coordinates of histogram counts/frequencies
            initial_guess: Optional initial parameter guess (amplitude, mean, stddev)
            
        Returns:
            Dict containing fit results and statistics
        """
        if len(bin_centers) != len(bin_counts):
            raise ValueError("bin_centers and bin_counts must have the same length")
        
        if len(bin_centers) < 3:
            raise ValueError("Need at least 3 data points to fit Gaussian")
        
        # Remove any NaN or infinite values
        valid_mask = np.isfinite(bin_centers) & np.isfinite(bin_counts) & (bin_counts >= 0)
        clean_centers = bin_centers[valid_mask]
        clean_counts = bin_counts[valid_mask]
        
        if len(clean_centers) < 3:
            raise ValueError("Not enough valid data points after cleaning")
        
        try:
            # Generate initial guess if not provided
            if initial_guess is None:
                initial_guess = self._generate_initial_guess(clean_centers, clean_counts)
            
            # Perform the curve fit
            popt, pcov = curve_fit(
                self._gaussian_function, 
                clean_centers, 
                clean_counts, 
                p0=initial_guess,
                maxfev=5000  # Increase max function evaluations
            )
            
            # Store results
            self.last_fit_params = popt
            self.last_fit_covariance = pcov
            
            # Calculate fit quality metrics
            fit_quality = self._calculate_fit_quality(clean_centers, clean_counts, popt)
            self.last_fit_quality = fit_quality
            
            # Extract parameters
            amplitude, mean, stddev = popt
            
            # Calculate parameter uncertainties from covariance matrix
            param_errors = np.sqrt(np.diag(pcov))
            
            # Generate fitted curve for plotting
            x_fit = np.linspace(np.min(clean_centers), np.max(clean_centers), 200)
            y_fit = self._gaussian_function(x_fit, *popt)
            
            # Calculate mode (peak location) - for Gaussian this is the mean
            mode_value = mean
            mode_bin_index = np.argmin(np.abs(clean_centers - mean))
            mode_bin_center = clean_centers[mode_bin_index]
            
            result = {
                'success': True,
                'fitted_params': {
                    'amplitude': amplitude,
                    'mean': mean,
                    'stddev': stddev
                },
                'param_errors': {
                    'amplitude_error': param_errors[0],
                    'mean_error': param_errors[1],
                    'stddev_error': param_errors[2]
                },
                'statistics': {
                    'peak_location': mean,  # Gaussian peak location
                    'peak_height': amplitude,  # Peak amplitude
                    'mode_bin_center': mode_bin_center,  # Nearest bin center to peak
                    'mode_bin_index': mode_bin_index,  # Index of mode bin
                    'fwhm': 2.355 * stddev,  # Full Width at Half Maximum
                    'area_under_curve': amplitude * stddev * np.sqrt(2 * np.pi)
                },
                'fit_quality': fit_quality,
                'fitted_curve': {
                    'x': x_fit,
                    'y': y_fit
                },
                'covariance_matrix': pcov,
                'original_data': {
                    'x': clean_centers,
                    'y': clean_counts
                }
            }
            
            logger.info(f"Gaussian fit successful - Mean: {mean:.3f}, Std: {stddev:.3f}, R²: {fit_quality['r_squared']:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Gaussian fitting failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'fitted_params': None,
                'statistics': None,
                'fit_quality': None,
                'fitted_curve': None
            }
    
    def fit_raw_data(self, size_data: np.ndarray, bins: int = 50) -> Dict[str, Any]:
        """
        Fit a Gaussian curve to raw measurement data by first creating a histogram.
        
        Args:
            size_data: Raw particle size measurements
            bins: Number of histogram bins to create
            
        Returns:
            Dict containing fit results and statistics
        """
        try:
            # Create histogram from raw data
            bin_counts, bin_edges = np.histogram(size_data, bins=bins)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Fit the histogram
            return self.fit_histogram_data(bin_centers, bin_counts)
            
        except Exception as e:
            logger.error(f"Raw data Gaussian fitting failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'fitted_params': None,
                'statistics': None,
                'fit_quality': None,
                'fitted_curve': None
            }
    
    def _gaussian_function(self, x: np.ndarray, amplitude: float, mean: float, stddev: float) -> np.ndarray:
        """
        Standard Gaussian function for curve fitting.
        
        Args:
            x: Independent variable
            amplitude: Peak height
            mean: Center of distribution
            stddev: Standard deviation
            
        Returns:
            Gaussian function values
        """
        return amplitude * np.exp(-((x - mean) ** 2) / (2 * stddev ** 2))
    
    def _generate_initial_guess(self, x_data: np.ndarray, y_data: np.ndarray) -> Tuple[float, float, float]:
        """
        Generate reasonable initial guess for Gaussian parameters.
        
        Args:
            x_data: X coordinates
            y_data: Y coordinates
            
        Returns:
            Tuple of (amplitude, mean, stddev) initial guess
        """
        # Amplitude: use the maximum y value
        amplitude_guess = np.max(y_data)
        
        # Mean: use weighted average or peak location
        peak_index = np.argmax(y_data)
        mean_guess = x_data[peak_index]
        
        # Alternative: weighted mean (often more robust)
        if np.sum(y_data) > 0:
            weighted_mean = np.sum(x_data * y_data) / np.sum(y_data)
            mean_guess = weighted_mean
        
        # Standard deviation: estimate from data spread
        # Use the range containing ~68% of the data
        data_range = np.max(x_data) - np.min(x_data)
        stddev_guess = data_range / 4  # Conservative estimate
        
        # Alternative: calculate moment-based estimate
        if np.sum(y_data) > 0:
            variance = np.sum(y_data * (x_data - mean_guess) ** 2) / np.sum(y_data)
            stddev_guess = np.sqrt(variance)
        
        logger.debug(f"Initial guess: amplitude={amplitude_guess:.2f}, mean={mean_guess:.2f}, stddev={stddev_guess:.2f}")
        
        return (amplitude_guess, mean_guess, stddev_guess)
    
    def _calculate_fit_quality(self, x_data: np.ndarray, y_data: np.ndarray, 
                              fit_params: Tuple[float, float, float]) -> Dict[str, float]:
        """
        Calculate various metrics to assess the quality of the Gaussian fit.
        
        Args:
            x_data: X coordinates of original data
            y_data: Y coordinates of original data
            fit_params: Fitted Gaussian parameters (amplitude, mean, stddev)
            
        Returns:
            Dict containing fit quality metrics
        """
        # Calculate fitted values
        y_fit = self._gaussian_function(x_data, *fit_params)
        
        # R-squared (coefficient of determination)
        ss_res = np.sum((y_data - y_fit) ** 2)  # Sum of squares of residuals
        ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)  # Total sum of squares
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Root Mean Square Error
        rmse = np.sqrt(np.mean((y_data - y_fit) ** 2))
        
        # Mean Absolute Error
        mae = np.mean(np.abs(y_data - y_fit))
        
        # Normalized RMSE (as percentage of data range)
        data_range = np.max(y_data) - np.min(y_data)
        nrmse = (rmse / data_range * 100) if data_range > 0 else float('inf')
        
        # Chi-squared statistic (assuming Poisson statistics for counts)
        # For count data, variance ≈ mean, so weight by 1/sqrt(y_data)
        weights = 1 / np.sqrt(np.maximum(y_data, 1))  # Avoid division by zero
        chi_squared = np.sum(weights * (y_data - y_fit) ** 2)
        
        # Reduced chi-squared (chi-squared per degree of freedom)
        dof = len(y_data) - 3  # 3 parameters in Gaussian
        reduced_chi_squared = chi_squared / dof if dof > 0 else float('inf')
        
        return {
            'r_squared': r_squared,
            'rmse': rmse,
            'mae': mae,
            'nrmse_percent': nrmse,
            'chi_squared': chi_squared,
            'reduced_chi_squared': reduced_chi_squared,
            'degrees_of_freedom': dof
        }
    
    def get_fit_summary(self) -> Optional[str]:
        """
        Get a formatted summary of the last fit results.
        
        Returns:
            Formatted string summary or None if no fit performed
        """
        if self.last_fit_params is None:
            return None
        
        amplitude, mean, stddev = self.last_fit_params
        quality = self.last_fit_quality
        
        summary = f"""Gaussian Fit Results:
  Peak Location (μ): {mean:.3f}
  Standard Deviation (σ): {stddev:.3f}
  Peak Height (A): {amplitude:.3f}
  FWHM: {2.355 * stddev:.3f}
  
Fit Quality:
  R²: {quality['r_squared']:.4f}
  RMSE: {quality['rmse']:.3f}
  Reduced χ²: {quality['reduced_chi_squared']:.3f}
"""
        return summary
    
    def get_fit_quality_category(self, good_r_squared: float = 0.85, okay_r_squared: float = 0.70,
                            good_chi_squared: float = 1.5, okay_chi_squared: float = 3.0) -> str:
        """
        Assess the fit quality in three categories: 'good', 'okay', or 'poor'.
        
        Args:
            good_r_squared: Minimum R² for 'good' fit
            okay_r_squared: Minimum R² for 'okay' fit  
            good_chi_squared: Maximum reduced χ² for 'good' fit
            okay_chi_squared: Maximum reduced χ² for 'okay' fit
            
        Returns:
            str: 'good', 'okay', or 'poor'
        """
        if self.last_fit_quality is None:
            return 'poor'
        
        r_squared = self.last_fit_quality['r_squared']
        reduced_chi_squared = self.last_fit_quality['reduced_chi_squared']
        
        # Good fit: both metrics meet high standards
        if r_squared >= good_r_squared and reduced_chi_squared <= good_chi_squared:
            return 'good'
        
        # Okay fit: both metrics meet moderate standards OR one is good and other is okay
        elif ((r_squared >= okay_r_squared and reduced_chi_squared <= okay_chi_squared) or
            (r_squared >= good_r_squared and reduced_chi_squared <= okay_chi_squared) or  
            (r_squared >= okay_r_squared and reduced_chi_squared <= good_chi_squared)):
            return 'okay'
        
        # Poor fit: fails to meet even moderate standards
        else:
            return 'poor'

    # Keep the original method for backward compatibility, but make it use the new logic
    def is_good_fit(self, min_r_squared: float = 0.85, max_reduced_chi_squared: float = 1.5) -> bool:
        """
        Assess whether the last fit meets quality criteria (backward compatibility).
        Now returns True only for 'good' fits.
        """
        return self.get_fit_quality_category() == 'good'

    # Add a new method for checking if fit is at least okay
    def is_acceptable_fit(self) -> bool:
        """Check if fit is at least 'okay' quality."""
        quality = self.get_fit_quality_category()
        return quality in ['good', 'okay']