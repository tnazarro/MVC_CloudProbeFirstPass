"""
PDF report generation module for particle data analysis with dataset information.
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import matplotlib.pyplot as plt
import matplotlib.figure
import traceback
from config.constants import REPORT_MARGIN

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.platypus import PageBreak
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)

class PDFReportGenerator:
    """Generates PDF reports for particle data analysis."""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=18,
            textColor=colors.darkblue,
            spaceAfter=20,
            alignment=1  # Center alignment
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceBefore=15,
            spaceAfter=10
        ))
        
        # Data style for statistics
        self.styles.add(ParagraphStyle(
            name='DataText',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Courier'
        ))
        
        # Notes style
        self.styles.add(ParagraphStyle(
            name='NotesText',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=5,
            spaceAfter=10
        ))
    
    def generate_report(self, 
                    output_path: str,
                    plot_figures: List[matplotlib.figure.Figure],
                    report_info: Dict[str, Any]) -> bool:
        """
        Generate a PDF report with multiple plots in 4-per-page grid layout.
        
        Args:
            output_path: Path where PDF should be saved
            plot_figures: List of matplotlib figures to include
            report_info: Report metadata (serial number, title, etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"DEBUG: Starting report generation")
            logger.info(f"DEBUG: plot_figures type: {type(plot_figures)}, length: {len(plot_figures)}")
            logger.info(f"DEBUG: report_info: {report_info}")
            # Create the PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin= REPORT_MARGIN,
                leftMargin= REPORT_MARGIN,
                topMargin= REPORT_MARGIN,
                bottomMargin= REPORT_MARGIN
            )
            
            # Build the story (content)
            story = []
            
            # Title page / header
            story.extend(self._create_header(report_info))
            
            #Force page break after header so plots start fresh
            story.append(PageBreak())

            # Add plots in 4-per-page grid layout
            story.extend(self._create_multi_plot_pages(plot_figures))
            
            # Footer
            story.extend(self._create_footer())
            
            # Build the PDF
            doc.build(story)
            
            logger.info(f"PDF report generated successfully with {len(plot_figures)} plots: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return False

    def _create_multi_plot_pages(self, plot_figures: List[matplotlib.figure.Figure]) -> list:
        """Create pages with 4-per-page grid layout of plots."""
        story = []
        
        # Process figures in chunks of 4
        for page_num, chunk_start in enumerate(range(0, len(plot_figures), 4)):
            chunk = plot_figures[chunk_start:chunk_start + 4]
            
            # Create 2x2 grid for this page
            story.extend(self._create_plot_grid(chunk))
            
            # Add page break if not the last page
            if chunk_start + 4 < len(plot_figures):
                story.append(PageBreak())
        
        return story

    def _create_plot_grid(self, figures: List[matplotlib.figure.Figure]) -> list:
        """Create a 2x2 grid of plots for one page."""
        story = []
        
        # Convert figures to ReportLab Images
        images = []
        for fig in figures:
            img = self._figure_to_image(fig)
            if img:
                images.append(img)
        
        # Pad with empty spacers if fewer than 4 plots
        while len(images) < 4:
            images.append(Spacer(1, 1))  # Invisible placeholder
        
        # Create 2x2 table: [[img1, img2], [img3, img4]]
        table_data = [
            [images[0], images[1]],
            [images[2], images[3]]
        ]
        
        # Calculate cell dimensions for letter page
        # Usable area: 540 x 720 points (after margins)
        cell_width = 270  # Half of 540
        cell_height = 310  # Leave some vertical spacing; reduced to fit on one page with header
        
        plot_table = Table(table_data, colWidths=[cell_width, cell_width],
                        rowHeights=[cell_height, cell_height])
        
        plot_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        story.append(plot_table)
        return story

    def _figure_to_image(self, fig: matplotlib.figure.Figure, 
                        width: float = 3.5*inch, height: float = 2.8*inch):
        """
        Convert matplotlib figure to ReportLab Image.
        
        Args:
            fig: Matplotlib figure to convert
            width: Desired width in ReportLab units (points)
            height: Desired height in ReportLab units (points)
            
        Returns:
            ReportLab Image object or None if conversion fails
        """
        try:
            # Save figure to bytes buffer
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            
            # Create ReportLab Image with specified dimensions
            img = Image(img_buffer, width=width, height=height)
            
            return img
            
        except Exception as e:
            logger.error(f"Failed to convert figure to image: {e}")
            return None

    def _create_header(self, report_info: Dict[str, Any]) -> list:
        """Create simplified header for multi-plot verification report."""
        elements = []
        
        # Main title
        title_text = report_info.get('custom_title') or 'Particle Size Distribution Verification Report'
        title = Paragraph(title_text, self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Report metadata table
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        metadata = [
            ['Report Generated:', timestamp],
            ['Instrument Serial Number:', report_info.get('instrument_serial_number', 'Not specified')],
            ['Number of Calibrations:', str(report_info.get('plot_count', 0))],
        ]
        
        metadata_table = Table(metadata, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(metadata_table)
        elements.append(Spacer(1, 20))
        
        # Brief description
        description = Paragraph(
            "This report contains particle size distribution histograms for verification of instrument calibration. "
            "Each plot shows the response to a specific glass bead size with Gaussian curve fitting and statistical analysis.",
            self.styles['Normal']
        )
        elements.append(description)
        elements.append(Spacer(1, 30))
        
        return elements
       
    def _create_footer(self) -> list:
        """Create the report footer section."""
        elements = []
        
        # Add page break before footer if needed
        elements.append(Spacer(1, 30))
        
        # Software info
        footer_text = Paragraph(
            "<i>Report generated by Particle Data Analyzer v1.0</i>",
            self.styles['Normal']
        )
        elements.append(footer_text)
        
        return elements