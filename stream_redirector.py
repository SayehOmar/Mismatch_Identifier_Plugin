from PyQt5.QtCore import QObject, pyqtSignal

class StreamRedirector(QObject):
    text_written = pyqtSignal(str)
    
    def __init__(self, original_stdout, text_widget=None):
        super().__init__()
        self.original_stdout = original_stdout
        self.text_widget = text_widget  # Optional direct reference

    def write(self, text):
        if not text.strip():  # Skip empty lines
            return
            
        # Always write to original stdout first
        if self.original_stdout:
            self.original_stdout.write(text)
            self.original_stdout.flush()
        
        # Try emitting signal first (preferred method)
        if text.strip():
            self.text_written.emit(text.strip())
            
        # Fallback: Try direct widget access
        if self.text_widget:
            try:
                self.text_widget.append(text.strip())
            except:
                pass  # Ignore errors

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()