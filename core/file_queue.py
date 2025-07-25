"""
File queue management for multi-file loading in particle data analyzer.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class FileQueue:
    """Manages a queue of files for batch processing with preview workflow."""
    
    def __init__(self):
        self.files: List[Dict[str, Any]] = []
        self.current_index: int = 0
        self.processed_files: List[Dict[str, Any]] = []
        self.failed_files: List[Dict[str, Any]] = []
        self.skipped_files: List[Dict[str, Any]] = []
        
    def add_files(self, file_paths: List[str]) -> int:
        """
        Add multiple files to the processing queue.
        
        Args:
            file_paths: List of file paths to add
            
        Returns:
            int: Number of files successfully added
        """
        added_count = 0
        
        for file_path in file_paths:
            try:
                # Validate file exists
                if not Path(file_path).exists():
                    logger.warning(f"File does not exist: {file_path}")
                    continue
                
                # Extract filename for auto-tagging
                filename = Path(file_path).name
                auto_tag = self._generate_auto_tag(filename)
                
                # Create file entry
                file_entry = {
                    'file_path': file_path,
                    'filename': filename,
                    'auto_tag': auto_tag,
                    'skip_rows': 0,  # Default, can be changed in preview
                    'status': 'pending',  # pending, processed, failed, skipped
                    'dataset_id': None,  # Set when successfully loaded
                    'error_message': None,  # Set if processing fails
                    'added_at': datetime.now(),
                    'notes': ''  # User can add notes during preview
                }
                
                self.files.append(file_entry)
                added_count += 1
                
                logger.info(f"Added file to queue: {filename}")
                
            except Exception as e:
                logger.error(f"Error adding file {file_path}: {e}")
        
        logger.info(f"Added {added_count} files to queue. Total queue size: {len(self.files)}")
        return added_count
    
    def _generate_auto_tag(self, filename: str) -> str:
        """
        Generate an automatic numeric tag from filename.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Generated numeric tag (defaults to incremental if no number found)
        """
        import re
        
        # Remove extension
        base_name = Path(filename).stem
        
        # Try to extract numbers from filename
        numbers = re.findall(r'-?\d+\.?\d*', base_name)
        
        if numbers:
            # Use the first number found
            try:
                return str(float(numbers[0]))
            except ValueError:
                pass
        
        # If no number found, generate incremental tag based on existing files in queue
        existing_tags = []
        for file_entry in self.files:
            try:
                existing_tags.append(float(file_entry['auto_tag']))
            except (ValueError, TypeError):
                pass
        
        # Find next available integer
        next_tag = 1.0
        while next_tag in existing_tags:
            next_tag += 1.0
        
        return str(int(next_tag)) if next_tag == int(next_tag) else str(next_tag)
    
    def get_current_file(self) -> Optional[Dict[str, Any]]:
        """
        Get the current file for preview/processing.
        
        Returns:
            Dict or None: Current file entry or None if queue is empty/complete
        """
        if 0 <= self.current_index < len(self.files):
            return self.files[self.current_index].copy()  # Return copy to prevent external modification
        return None
    
    def get_current_file_info(self) -> Dict[str, Any]:
        """
        Get information about current position in queue.
        
        Returns:
            Dict: Queue position and status information
        """
        return {
            'current_index': self.current_index,
            'total_files': len(self.files),
            'remaining_files': max(0, len(self.files) - self.current_index),
            'processed_count': len(self.processed_files),
            'failed_count': len(self.failed_files),
            'skipped_count': len(self.skipped_files),
            'has_current_file': self.current_index < len(self.files),
            'is_complete': self.current_index >= len(self.files)
        }
    
    def update_current_file(self, **kwargs) -> bool:
        """
        Update properties of the current file.
        
        Args:
            **kwargs: Properties to update (skip_rows, auto_tag, notes, etc.)
            
        Returns:
            bool: True if successful, False if no current file
        """
        if not (0 <= self.current_index < len(self.files)):
            return False
        
        # Update allowed properties
        allowed_updates = ['skip_rows', 'auto_tag', 'notes']
        current_file = self.files[self.current_index]
        
        for key, value in kwargs.items():
            if key in allowed_updates:
                current_file[key] = value
                logger.debug(f"Updated {key} for file {current_file['filename']}: {value}")
        
        return True
    
    def next_file(self) -> bool:
        """
        Move to the next file in the queue.
        
        Returns:
            bool: True if moved to next file, False if at end of queue
        """
        if self.current_index < len(self.files) - 1:
            self.current_index += 1
            logger.debug(f"Moved to next file: index {self.current_index}")
            return True
        
        # If we're at the last file, move past it to indicate completion
        if self.current_index == len(self.files) - 1:
            self.current_index += 1
            logger.info("Reached end of file queue")
        
        return False
    
    def previous_file(self) -> bool:
        """
        Move to the previous file in the queue.
        
        Returns:
            bool: True if moved to previous file, False if at beginning
        """
        if self.current_index > 0:
            self.current_index -= 1
            logger.debug(f"Moved to previous file: index {self.current_index}")
            return True
        return False
    
    def skip_current_file(self, reason: str = "User skipped") -> bool:
        """
        Skip the current file and move to next.
        
        Args:
            reason: Reason for skipping
            
        Returns:
            bool: True if file was skipped, False if no current file
        """
        current_file = self.get_current_file()
        if not current_file:
            return False
        
        # Update file status
        self.files[self.current_index]['status'] = 'skipped'
        self.files[self.current_index]['error_message'] = reason
        
        # Move to skipped list
        skipped_file = self.files[self.current_index].copy()
        self.skipped_files.append(skipped_file)
        
        logger.info(f"Skipped file: {current_file['filename']} - {reason}")
        
        # Move to next file
        self.next_file()
        return True
    
    def mark_current_processed(self, dataset_id: str) -> bool:
        """
        Mark the current file as successfully processed.
        
        Args:
            dataset_id: ID of the dataset created from this file
            
        Returns:
            bool: True if marked successfully, False if no current file
        """
        current_file = self.get_current_file()
        if not current_file:
            return False
        
        # Update file status
        self.files[self.current_index]['status'] = 'processed'
        self.files[self.current_index]['dataset_id'] = dataset_id
        
        # Move to processed list
        processed_file = self.files[self.current_index].copy()
        self.processed_files.append(processed_file)
        
        logger.info(f"Marked file as processed: {current_file['filename']} -> dataset {dataset_id}")
        
        # Move to next file
        self.next_file()
        return True
    
    def mark_current_failed(self, error_message: str) -> bool:
        """
        Mark the current file as failed to process.
        
        Args:
            error_message: Error description
            
        Returns:
            bool: True if marked successfully, False if no current file
        """
        current_file = self.get_current_file()
        if not current_file:
            return False
        
        # Update file status
        self.files[self.current_index]['status'] = 'failed'
        self.files[self.current_index]['error_message'] = error_message
        
        # Move to failed list
        failed_file = self.files[self.current_index].copy()
        self.failed_files.append(failed_file)
        
        logger.error(f"Marked file as failed: {current_file['filename']} - {error_message}")
        
        # Move to next file
        self.next_file()
        return True
    
    def has_more_files(self) -> bool:
        """
        Check if there are more files to process.
        
        Returns:
            bool: True if more files remain, False if queue is complete
        """
        return self.current_index < len(self.files)
    
    def reset_to_beginning(self) -> None:
        """Reset queue to beginning for reprocessing."""
        self.current_index = 0
        # Clear processed lists but keep the file entries with their current status
        self.processed_files.clear()
        self.failed_files.clear()
        self.skipped_files.clear()
        
        # Reset all file statuses to pending
        for file_entry in self.files:
            file_entry['status'] = 'pending'
            file_entry['dataset_id'] = None
            file_entry['error_message'] = None
        
        logger.info("Reset file queue to beginning")
    
    def clear_queue(self) -> None:
        """Clear all files from the queue."""
        self.files.clear()
        self.current_index = 0
        self.processed_files.clear()
        self.failed_files.clear()
        self.skipped_files.clear()
        logger.info("Cleared file queue")
    
    def get_all_files(self) -> List[Dict[str, Any]]:
        """
        Get all files in queue with their current status.
        
        Returns:
            List[Dict]: All files with status information
        """
        return [file_entry.copy() for file_entry in self.files]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of queue processing status.
        
        Returns:
            Dict: Summary information
        """
        info = self.get_current_file_info()
        
        return {
            'total_files': info['total_files'],
            'current_position': info['current_index'] + 1 if info['has_current_file'] else info['total_files'],
            'processed': info['processed_count'],
            'failed': info['failed_count'],
            'skipped': info['skipped_count'],
            'remaining': info['remaining_files'],
            'is_complete': info['is_complete'],
            'success_rate': info['processed_count'] / max(1, info['total_files']) * 100 if info['total_files'] > 0 else 0
        }
    
    def jump_to_file(self, index: int) -> bool:
        """
        Jump to a specific file in the queue.
        
        Args:
            index: Index of file to jump to
            
        Returns:
            bool: True if successful, False if invalid index
        """
        if 0 <= index < len(self.files):
            self.current_index = index
            logger.debug(f"Jumped to file index {index}")
            return True
        return False
