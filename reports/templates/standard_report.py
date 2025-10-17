"""
Standard report template for particle size analysis.
"""

from typing import Dict, Any, Optional, List
import matplotlib.figure
from ..pdf_generator import PDFReportGenerator


class StandardReportTemplate:
    """Standard template for particle analysis reports."""
    
    def __init__(self):
        self.generator = PDFReportGenerator()
    
    def create_report(self,
                    output_path: str,
                    plot_figures: List[matplotlib.figure.Figure], 
                    instrument_serial_number: str, 
                    custom_title: Optional[str] = None) -> bool:
        """
        Create a standard particle analysis report with multiple plots.
        
        Args:
            output_path: Where to save the PDF
            plot_figures: List of matplotlib figures to include in report
            instrument_serial_number: Serial number of the instrument being tested
            custom_title: Optional custom report title
            
        Returns:
            bool: Success status
        """
        
        
        # Build report metadata
        report_info = {
            'instrument_serial_number': instrument_serial_number,
            'custom_title': custom_title,
            'plot_count': len(plot_figures)
        }
        
        return self.generator.generate_report(
            output_path=output_path,
            plot_figures=plot_figures,
            report_info=report_info
        )

    
    def _prepare_analysis_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure analysis parameters have default values."""
        defaults = {
            'data_mode': 'pre_aggregated',
            'bin_count': 50,
            'size_column': 'Unknown',
            'frequency_column': None,
            'skip_rows': 0,
            'show_stats_lines': True
        }
        
        # Merge with provided params
        enhanced = defaults.copy()
        enhanced.update(params)
        
        return enhanced