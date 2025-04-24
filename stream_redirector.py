from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class StreamRedirector(QObject):
    text_written = pyqtSignal(str)
    
    def __init__(self, original_stdout, text_widget=None, delay_ms=1):
        super().__init__()
        self.original_stdout = original_stdout
        self.text_widget = text_widget
        self.delay_ms = delay_ms
        self.message_queue = []
        
        # Create a timer for processing messages with delay
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_next_message)
        self.timer.setSingleShot(False)  # Continuous timer
        
    def start_timer(self):
        if not self.timer.isActive():
            self.timer.start(self.delay_ms)
    
    def process_next_message(self):
        if self.message_queue:
            message = self.message_queue.pop(0)
            self.text_written.emit(message)
            
            # If queue is empty, stop the timer
            if not self.message_queue:
                self.timer.stop()
                
    def write(self, text):
        if not text.strip():  # Skip empty lines
            return
            
        # Always write to original stdout first
        if self.original_stdout:
            self.original_stdout.write(text)
            self.original_stdout.flush()
        
        # Add text to queue for delayed display
        if text.strip():
            self.message_queue.append(text.strip())
            self.start_timer()
            
        # Fallback: Try direct widget access
        if self.text_widget:
            try:
                self.text_widget.append(text.strip())
            except:
                pass  # Ignore errors

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()