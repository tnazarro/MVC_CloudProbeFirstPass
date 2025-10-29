"""
Enhanced plotting module for particle data visualization with Gaussian curve fitting.
"""

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
import logging
from typing import Optional, Tuple, Dict, Any
from config.constants import PLOT_WIDTH, PLOT_HEIGHT, PLOT_DPI, DEFAULT_BIN_COUNT

# Import the new Gaussian fitter
try:
    from core.gaussian_fitter import GaussianFitter
    GAUSSIAN_FITTING_AVAILABLE = True
except ImportError:
    GAUSSIAN_FITTING_AVAILABLE = False
    logging.warning("Gaussian fitting not available - scipy may not be installed")

# Set matplotlib to use Agg backend before importing pyplot to avoid threading issues
import matplotlib
matplotlib.use('Agg')

logger = logging.getLogger(__name__)

class ParticlePlotter:
    """Enhanced plotter with Gaussian curve fitting capabilities."""
    
    def __init__(self):
        self.figure = None
        self.ax = None
        self.gaussian_fitter = GaussianFitter() if GAUSSIAN_FITTING_AVAILABLE else None
        self.last_gaussian_fit = None
        self._setup_matplotlib()
    
    def _setup_matplotlib(self):
        """Configure matplotlib settings."""
        plt.style.use('default')  # Use default style for now
    
    def create_histogram(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray] = None, 
                        bin_count: int = DEFAULT_BIN_COUNT, title: str = "Particle Size Distribution", 
                        show_stats_lines: bool = True, data_mode: str = "pre_aggregated",
                        show_gaussian_fit: bool = True,
                        metadata: Optional[Dict[str, Any]] = None) -> matplotlib.figure.Figure:
        """
        Create a histogram plot of particle size data with optional Gaussian curve fitting.
        
        Args:
            size_data: Array of particle sizes
            frequency_data: Optional array of frequencies (ignored for raw measurements)
            bin_count: Number of bins for the histogram
            title: Plot title
            show_stats_lines: Whether to show mean and std deviation lines
            data_mode: "pre_aggregated" or "raw_measurements"
            show_gaussian_fit: Whether to show Gaussian curve fit
            
        Returns:
            matplotlib Figure object
        """
        try:
            # Close any existing figure to prevent memory leaks
            if self.figure is not None:
                plt.close(self.figure)
                self.figure = None
            
            # Create figure with explicit new figure number to avoid ID conflicts
            self.figure = plt.figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
            self.ax = self.figure.add_subplot(111)
            
            # Create histogram based on data mode
            if data_mode == "raw_measurements":
                # Raw measurements: create histogram from individual data points
                n, bins, patches = self.ax.hist(size_data, bins=bin_count, alpha=0.7, 
                                               edgecolor='black', linewidth=0.5, 
                                               label='Data')
                self.ax.set_ylabel('Count')
                logger.info(f"Created raw measurements histogram from {len(size_data)} individual measurements")
                
                # For Gaussian fitting, use histogram data
                bin_centers = (bins[:-1] + bins[1:]) / 2
                bin_counts = n
                
            elif data_mode == "pre_aggregated" and frequency_data is not None:
                # Pre-aggregated with frequency data: weighted histogram
                n, bins, patches = self.ax.hist(size_data, bins=bin_count, weights=frequency_data, 
                                               alpha=0.7, edgecolor='black', linewidth=0.5,
                                               label='Data')
                self.ax.set_ylabel('Frequency')
                logger.info(f"Created pre-aggregated histogram with {len(size_data)} bins and frequency weights")
                
                # For Gaussian fitting, use the original binned data
                bin_centers = size_data
                bin_counts = frequency_data
                
            else:
                # Fallback: simple count histogram
                n, bins, patches = self.ax.hist(size_data, bins=bin_count, alpha=0.7, 
                                               edgecolor='black', linewidth=0.5,
                                               label='Data')
                self.ax.set_ylabel('Count')
                logger.info(f"Created fallback count histogram from {len(size_data)} data points")
                
                # For Gaussian fitting, use histogram data
                bin_centers = (bins[:-1] + bins[1:]) / 2
                bin_counts = n
            
            # Calculate mode (bin with highest count) 
            mode_index = np.argmax(n)
            mode_bin_center = bin_centers[mode_index]
            mode_bin_left = bins[mode_index]
            mode_bin_right = bins[mode_index + 1]
            mode_info = {
                'center': mode_bin_center,
                'left': mode_bin_left,
                'right': mode_bin_right
            }
            
            self.ax.set_xlabel('Particle Size')
            self.ax.set_title(title)
            self.ax.grid(True, alpha=0.3)
            
            # Perform Gaussian fitting if requested and available
            gaussian_fit_result = None
            if show_gaussian_fit and self.gaussian_fitter is not None:
                try:
                    gaussian_fit_result = self.gaussian_fitter.fit_histogram_data(bin_centers, bin_counts)
                    self.last_gaussian_fit = gaussian_fit_result
                    
                    if gaussian_fit_result['success']:
                        self._add_gaussian_curve(gaussian_fit_result)
                        logger.info("Gaussian curve fit added to plot")
                    else:
                        logger.warning(f"Gaussian fitting failed: {gaussian_fit_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"Error during Gaussian fitting: {e}")
            
            # Calculate statistics for vertical lines (use fitted parameters if available)
            if gaussian_fit_result and gaussian_fit_result['success']:
                # Use Gaussian fit parameters
                fit_params = gaussian_fit_result['fitted_params']
                mean_size = fit_params['mean']
                std_size = fit_params['stddev']
                
               # Add fit information to stats text
                stats_text = self._create_stats_text_with_gaussian(size_data, frequency_data, 
                                                                 data_mode, gaussian_fit_result,
                                                                 mode_info, metadata)
            else:
                # Use traditional statistical calculation
                if data_mode == "raw_measurements":
                    mean_size = np.mean(size_data)
                    std_size = np.std(size_data)
                elif data_mode == "pre_aggregated" and frequency_data is not None:
                    mean_size = np.average(size_data, weights=frequency_data)
                    variance = np.average((size_data - mean_size)**2, weights=frequency_data)
                    std_size = np.sqrt(variance)
                else:
                    mean_size = np.mean(size_data)
                    std_size = np.std(size_data)
                
                # Add basic statistics to the plot
                stats_text = self._create_basic_stats_text(size_data, frequency_data, data_mode,
                                                          mode_info, metadata)
            
            # Add statistical reference lines
            if show_stats_lines:
                self._add_statistical_lines(mean_size, std_size)
            
            # Add statistics text box
            self.ax.text(0.02, 0.98, stats_text, transform=self.ax.transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', 
                        facecolor='white', alpha=0.8), fontsize=9)
            
            # Add legend if we have multiple elements
            if show_gaussian_fit and gaussian_fit_result and gaussian_fit_result['success']:
                self.ax.legend(loc='upper right', fontsize=9)
            
            self.figure.tight_layout()

            logger.info(f"Created histogram with {bin_count} bins")
            
            return self.figure
            
        except Exception as e:
            logger.error(f"Error creating histogram: {e}")
            return None
    
    def _add_gaussian_curve(self, fit_result: Dict[str, Any]) -> None:
        """Add the fitted Gaussian curve to the plot."""
        if not fit_result['success']:
            return
        
        try:
            curve_x = fit_result['fitted_curve']['x']
            curve_y = fit_result['fitted_curve']['y']
            
            # Plot the Gaussian curve
            self.ax.plot(curve_x, curve_y, 'r--', linewidth=2, 
                        label='Gaussian Fit', alpha=0.8)
            
            # Add peak marker
            peak_x = fit_result['fitted_params']['mean']
            peak_y = fit_result['fitted_params']['amplitude']
            self.ax.plot(peak_x, peak_y, 'ro', markersize=6, 
                        label=f'Peak: {peak_x:.2f}')
            
            logger.info(f"Added Gaussian curve with peak at {peak_x:.3f}")
            
        except Exception as e:
            logger.error(f"Error adding Gaussian curve: {e}")
    
    def _create_stats_text_with_gaussian(self, size_data: np.ndarray, 
                                    frequency_data: Optional[np.ndarray],
                                    data_mode: str, 
                                    fit_result: Dict[str, Any],
                                    mode_info: Dict[str, float],
                                    metadata: Optional[Dict[str, Any]]) -> str:
        """Create statistics text including Gaussian fit parameters and metadata."""
        fit_params = fit_result['fitted_params']
        stats_text = ''
        
        # Add metadata header
        if metadata:
            if metadata.get('bead_size'):
                stats_text += f"Bead: {metadata['bead_size']} μm\n"
            
            # Material - show placeholder if not available
            if metadata.get('material'):
                stats_text += f"Material: {metadata['material']}\n"
            else:
                stats_text += "Material: TBD\n"
            
            # Lot number - show placeholder if not available
            if metadata.get('lot_number'):
                stats_text += f"Lot: {metadata['lot_number']}\n"
            else:
                stats_text += "Lot: TBD\n"
            
            if metadata.get('serial_number'):
                stats_text += f"S/N: {metadata['serial_number']}\n"
            if metadata.get('filename'):
                stats_text += f"File: {metadata['filename']}\n"
            if metadata.get('timestamp'):
                # Extract just the date (YYYY-MM-DD)
                date_only = metadata['timestamp'].split(' ')[0]
                stats_text += f"Date: {date_only}\n"
            stats_text += '\n'  # Blank line separator
        
        # Statistical values
        stats_text += f"Peak: {fit_params['mean']:.2f}\n"
        stats_text += f"Mode: {mode_info['center']:.2f} ({mode_info['left']:.2f}-{mode_info['right']:.2f})\n"
        stats_text += f"Std: {fit_params['stddev']:.2f}\n"
        
        # Total count
        if data_mode == "raw_measurements":
            n_measurements = len(size_data)
            stats_text += f'Total: {n_measurements}'
        else:
            stats_text += f'Total: {len(size_data)}'
        
        return stats_text
    
    def _create_basic_stats_text(self, size_data: np.ndarray, 
                               frequency_data: Optional[np.ndarray],
                               data_mode: str,
                               mode_info: Dict[str, float],
                               metadata: Optional[Dict[str, Any]]) -> str:
        """Create basic statistics text without Gaussian fit."""
        stats_text = ''
        
        # Add metadata header
        if metadata:
            if metadata.get('bead_size'):
                stats_text += f"Bead: {metadata['bead_size']} μm\n"
            
            # Material - show placeholder if not available
            if metadata.get('material'):
                stats_text += f"Material: {metadata['material']}\n"
            else:
                stats_text += "Material: TBD\n"
            
            # Lot number - show placeholder if not available
            if metadata.get('lot_number'):
                stats_text += f"Lot: {metadata['lot_number']}\n"
            else:
                stats_text += "Lot: TBD\n"
            
            if metadata.get('serial_number'):
                stats_text += f"S/N: {metadata['serial_number']}\n"
            if metadata.get('filename'):
                stats_text += f"File: {metadata['filename']}\n"
            if metadata.get('timestamp'):
                # Extract just the date (YYYY-MM-DD)
                date_only = metadata['timestamp'].split(' ')[0]
                stats_text += f"Date: {date_only}\n"
            stats_text += '\n'  # Blank line separator
        
        # Calculate statistics
        if data_mode == "raw_measurements":
            mean_size = np.mean(size_data)
            std_size = np.std(size_data)
            n_measurements = len(size_data)
            
            stats_text += f'Mean: {mean_size:.2f}\n'
            stats_text += f"Mode: {mode_info['center']:.2f} ({mode_info['left']:.2f}-{mode_info['right']:.2f})\n"
            stats_text += f'Std: {std_size:.2f}\n'
            stats_text += f'Total: {n_measurements}'
            
        elif data_mode == "pre_aggregated" and frequency_data is not None:
            mean_size = np.average(size_data, weights=frequency_data)
            variance = np.average((size_data - mean_size)**2, weights=frequency_data)
            std_size = np.sqrt(variance)
            total_frequency = np.sum(frequency_data)
            
            stats_text += f'Mean: {mean_size:.2f}\n'
            stats_text += f"Mode: {mode_info['center']:.2f} ({mode_info['left']:.2f}-{mode_info['right']:.2f})\n"
            stats_text += f'Std: {std_size:.2f}\n'
            stats_text += f'Total: {total_frequency:.0f}'
            
        else:
            mean_size = np.mean(size_data)
            std_size = np.std(size_data)
            
            stats_text += f'Mean: {mean_size:.2f}\n'
            stats_text += f"Mode: {mode_info['center']:.2f} ({mode_info['left']:.2f}-{mode_info['right']:.2f})\n"
            stats_text += f'Std: {std_size:.2f}\n'
            stats_text += f'Total: {len(size_data)}'
        
        return stats_text
    
    def _add_statistical_lines(self, mean: float, std: float):
        """Add vertical lines for mean and standard deviations."""
        try:
            # Get the y-axis limits to draw full-height lines
            y_min, y_max = self.ax.get_ylim()
            
            # Mean line (solid, prominent)
            self.ax.axvline(mean, color='red', linestyle='-', linewidth=2, 
                           alpha=0.8, label=f'Mean: {mean:.2f}')
            
            # Standard deviation lines
            # 1 sigma lines (dashed)
            self.ax.axvline(mean - std, color='orange', linestyle='--', linewidth=1.5, 
                           alpha=0.7, label=f'±1σ: {mean-std:.2f}, {mean+std:.2f}')
            self.ax.axvline(mean + std, color='orange', linestyle='--', linewidth=1.5, 
                           alpha=0.7)
            
            # 2 sigma lines (dotted)
            self.ax.axvline(mean - 2*std, color='purple', linestyle=':', linewidth=1.5, 
                           alpha=0.6, label=f'±2σ: {mean-2*std:.2f}, {mean+2*std:.2f}')
            self.ax.axvline(mean + 2*std, color='purple', linestyle=':', linewidth=1.5, 
                           alpha=0.6)
            
            # Add shaded regions for standard deviation zones
            self.ax.axvspan(mean - std, mean + std, alpha=0.1, color='orange', 
                           label='1σ region (68%)')
            self.ax.axvspan(mean - 2*std, mean - std, alpha=0.05, color='purple')
            self.ax.axvspan(mean + std, mean + 2*std, alpha=0.05, color='purple')
            
            logger.info(f"Added statistical lines - Mean: {mean:.2f}, Std: {std:.2f}")
            
        except Exception as e:
            logger.error(f"Error adding statistical lines: {e}")
    
    def get_last_gaussian_fit(self) -> Optional[Dict[str, Any]]:
        """
        Get the results from the last Gaussian fit.
        
        Returns:
            Dict containing fit results or None if no fit performed
        """
        return self.last_gaussian_fit
    
    def get_gaussian_fit_summary(self) -> Optional[str]:
        """
        Get a formatted summary of the last Gaussian fit.
        
        Returns:
            Formatted string summary or None if no fit performed
        """
        if self.gaussian_fitter is not None:
            return self.gaussian_fitter.get_fit_summary()
        return None
    
    def save_plot(self, filename: str, dpi: int = 300):
        """Save the current plot to file."""
        if self.figure is None:
            logger.error("No plot to save")
            return False
        
        try:
            self.figure.savefig(filename, dpi=dpi, bbox_inches='tight')
            logger.info(f"Plot saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving plot: {e}")
            return False
    
    def update_bin_count(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray], 
                        new_bin_count: int, show_stats_lines: bool = True):
        """Update the histogram with a new bin count - DEPRECATED."""
        logger.warning("update_bin_count is deprecated - use create_histogram instead")
        return self.create_histogram(size_data, frequency_data, new_bin_count, 
                                   show_stats_lines=show_stats_lines)
    