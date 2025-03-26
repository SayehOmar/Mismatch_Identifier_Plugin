from PyQt5.QtWidgets import QProgressBar, QApplication

class ProgressBarManager:
    def __init__(self, progress_bar):
        """
        Initialize the Progress Bar Manager
        
        :param progress_bar: QProgressBar object to manage
        """
        self.progress_bar = progress_bar
        self.total_items = 0  # Initialize total_items
        self.current_progress = 0
    
    def reset(self):
        """
        Reset the progress bar to 0
        """
        self.progress_bar.setValue(0)
        self.current_progress = 0
        self.total_items = 0
    
    def set_total(self, total_items):
        """
        Set the total number of items to track
        
        :param total_items: Total number of items to process
        """
        self.total_items = total_items
        self.current_progress = 0
    
    def update_progress(self, processed_items=1):
        """
        Update the progress bar
        
        :param processed_items: Number of items processed in this update
        """
        # If total_items is not set, default to a safe value
        if self.total_items == 0:
            self.total_items = 1  # Prevent division by zero
        
        self.current_progress += processed_items
        
        # Calculate percentage
        progress_percentage = int((self.current_progress / self.total_items) * 100)
        
        # Ensure we don't exceed 100%
        progress_percentage = min(progress_percentage, 100)
        
        # Set progress bar value
        self.progress_bar.setValue(progress_percentage)
        
        # Process UI events to keep interface responsive
        QApplication.processEvents()
    
    def complete(self):
        """
        Ensure progress bar reaches 100%
        """
        self.progress_bar.setValue(100)

def create_progress_bar_manager(progress_bar):
    """
    Convenience function to create a ProgressBarManager
    
    :param progress_bar: QProgressBar object
    :return: ProgressBarManager instance
    """
    return ProgressBarManager(progress_bar)