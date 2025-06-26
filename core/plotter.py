"""
Plotting module for particle data visualization.
"""

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
import logging
from typing import Optional, Tuple
from config.constants import PLOT_WIDTH, PLOT_HEIGHT, PLOT_DPI, DEFAULT_BIN_COUNT

# Set matplotlib to use Agg backend before importing pyplot to avoid threading issues
import matplotlib
matplotlib.use('Agg')

logger = logging.getLogger(__name__)

class ParticlePlotter:
    """Handles plotting of particle sizing data."""
    
    def __init__(self):
        self.figure = None
        self.ax = None
        self._setup_matplotlib()
    
    def _setup_matplotlib(self):
        """Configure matplotlib settings."""
        plt.style.use('default')  # Use default style for now
    
    def create_histogram(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray] = None, 
                        bin_count: int = DEFAULT_BIN_COUNT, title: str = "Particle Size Distribution", 
                        show_stats_lines: bool = True) -> matplotlib.figure.Figure:
        """
        Create a histogram plot of particle size data.
        
        Args:
            size_data: Array of particle sizes
            frequency_data: Optional array of frequencies (if None, uses count histogram)
            bin_count: Number of bins for the histogram
            title: Plot title
            show_stats_lines: Whether to show mean and std deviation lines
            
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
            
            if frequency_data is not None:
                # Weighted histogram using frequency data
                self.ax.hist(size_data, bins=bin_count, weights=frequency_data, 
                           alpha=0.7, edgecolor='black', linewidth=0.5)
                self.ax.set_ylabel('Frequency')
            else:
                # Simple count histogram
                self.ax.hist(size_data, bins=bin_count, alpha=0.7, 
                           edgecolor='black', linewidth=0.5)
                self.ax.set_ylabel('Count')
            
            self.ax.set_xlabel('Particle Size')
            self.ax.set_title(title)
            self.ax.grid(True, alpha=0.3)
            
            # Calculate statistics for vertical lines
            if frequency_data is not None:
                # Weighted statistics
                mean_size = np.average(size_data, weights=frequency_data)
                variance = np.average((size_data - mean_size)**2, weights=frequency_data)
                std_size = np.sqrt(variance)
            else:
                # Simple statistics
                mean_size = np.mean(size_data)
                std_size = np.std(size_data)
            
            # Add statistical reference lines
            if show_stats_lines:
                self._add_statistical_lines(mean_size, std_size)
            
            # Add some basic statistics to the plot
            self._add_stats_text(size_data, frequency_data)
            
            self.figure.tight_layout()
            logger.info(f"Created histogram with {bin_count} bins")
            
            return self.figure
            
        except Exception as e:
            logger.error(f"Error creating histogram: {e}")
            return None
    
    def _add_stats_text(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray]):
        """Add statistics text box to the plot."""
        try:
            if frequency_data is not None:
                # Calculate weighted statistics
                weights = frequency_data / np.sum(frequency_data)
                mean_size = np.average(size_data, weights=frequency_data)
                # For weighted std, we need a more complex calculation
                variance = np.average((size_data - mean_size)**2, weights=frequency_data)
                std_size = np.sqrt(variance)
            else:
                mean_size = np.mean(size_data)
                std_size = np.std(size_data)
            
            stats_text = f'Mean: {mean_size:.2f}\nStd: {std_size:.2f}\nN: {len(size_data)}'
            
            # Add text box
            self.ax.text(0.02, 0.98, stats_text, transform=self.ax.transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', 
                        facecolor='white', alpha=0.8))
            
        except Exception as e:
            logger.error(f"Error adding stats text: {e}")
    
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
            
            # Add shaded regions for standard deviation zones (optional)
            self.ax.axvspan(mean - std, mean + std, alpha=0.1, color='orange', 
                           label='1σ region (68%)')
            self.ax.axvspan(mean - 2*std, mean - std, alpha=0.05, color='purple')
            self.ax.axvspan(mean + std, mean + 2*std, alpha=0.05, color='purple')
            
            # Add a legend for the statistical lines
            legend_elements = [
                plt.Line2D([0], [0], color='red', linewidth=2, label=f'Mean: {mean:.2f}'),
                plt.Line2D([0], [0], color='orange', linewidth=1.5, linestyle='--', 
                          label=f'±1σ ({mean-std:.2f}, {mean+std:.2f})'),
                plt.Line2D([0], [0], color='purple', linewidth=1.5, linestyle=':', 
                          label=f'±2σ ({mean-2*std:.2f}, {mean+2*std:.2f})')
            ]
            
            # Place legend in upper right, but check if it fits
            self.ax.legend(handles=legend_elements, loc='upper right', 
                          fontsize=9, framealpha=0.9)
            
            logger.info(f"Added statistical lines - Mean: {mean:.2f}, Std: {std:.2f}")
            
        except Exception as e:
            logger.error(f"Error adding statistical lines: {e}")
    
    def update_bin_count(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray], 
                        new_bin_count: int, show_stats_lines: bool = True):
        """Update the histogram with a new bin count."""
        # Don't reuse the old figure - create a new one instead
        # This method is now deprecated in favor of creating new figures
        logger.warning("update_bin_count is deprecated - use create_histogram instead")
        return self.create_histogram(size_data, frequency_data, new_bin_count, 
                                   show_stats_lines=show_stats_lines)
    
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