import os
import sys
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtCore

from .GridCapture import GridCapture
from .File_loader import FileLoader
from .grid_filter import GridFilter
from .mismatch_identifier_Logic import MismatchIdentifier
from .stream_redirector import StreamRedirector
from .white_remover import WhitePixelRemover


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "Mismatch_Identifier_Plugin_dialog_base.ui")
)

class Mismatch_Identifier_PluginDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(Mismatch_Identifier_PluginDialog, self).__init__(parent)
        
        QtCore.QCoreApplication.processEvents()
        self.setupUi(self)

        # Save original stdout/stderr
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr

        # ✅ Initialize output/error capturers with proper argument and delay
        self.output_capturer = StreamRedirector(self.stdout_backup, )
        self.error_capturer = StreamRedirector(self.stderr_backup, )

        # Redirect stdout/stderr
        sys.stdout = self.output_capturer
        sys.stderr = self.error_capturer

        # Find the QTextBrowser by its object name
        self.grid_creation_browser = self.findChild(QtWidgets.QTextBrowser, "GridCreation_ImagesCapturing")

        # Connect signals AFTER UI is created
        
        #self.error_capturer.text_written.connect(self.safe_append_to_image_browser)
        self.output_capturer.text_written.connect(self.safe_append_to_grid_creation_browser)
        # Connect the Start Process button
        self.Start_Process.clicked.connect(self.on_start_process_clicked)

        # Create a FileLoader instance
        self.file_loader = FileLoader(self)

        # Connect file loading buttons
        self.Sauvegarde_Avant_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Avant_AI, 'folder1_path')
        )
        self.Sauvegarde_Apres_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Apres_AI, 'folder2_path')
        )
        self.Styles_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Styles, 'style_folder_path')
        )

        # Connect actions
        self.Start_Process.clicked.connect(self.on_generate_grid)
        self.StartLoading.clicked.connect(self.file_loader.load_layers)

        # Placeholder for classifier
        self.classifier = None
    """
    def append_to_processing_log(self, message):
        #Safely append text to the image processing browser
        if self.image_processing_browser:
            try:
                self.image_processing_browser.append(str(message))
            except RuntimeError:
                pass
    """

    def safe_append_to_grid_creation_browser(self, message):
        if self.grid_creation_browser:
            try:
                self.grid_creation_browser.append(str(message))
                # Auto-scroll to the bottom
                scrollbar = self.grid_creation_browser.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except RuntimeError:
                pass


    
    """
    def safe_append_to_image_browser(self, message):
        if self.image_processing_browser:
            try:
                self.image_processing_browser.append(str(message))
            except RuntimeError:
                pass
    """
    def on_generate_grid(self):
        """Generate and filter the grid"""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(plugin_dir, "Grid", "grid.shp")
        reference_layer_name = "Arc_itineraire_AV"

        try:
            grid_filter = GridFilter(reference_layer_name, output_path)
            grid_filter.get_layer_by_name()
            grid_filter.generate_and_filter_grid()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def on_capture_grid_clicked(self):
        """Capture grid cell images and metadata"""
        try:
            # Get absolute plugin directory path
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            output_folder = os.path.join(plugin_dir, "GridCaptures")
            
            # Make sure the output directory exists
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                
            # Show starting message in text browser
            self.safe_append_to_grid_creation_browser("Starting grid cell capture...")
                
            # Temporarily redirect stdout to a dedicated redirector for GridCapture
            grid_capture_redirector = StreamRedirector(self.stdout_backup, delay_ms=100)
            grid_capture_redirector.text_written.connect(self.safe_append_to_grid_creation_browser)
            old_stdout = sys.stdout
            sys.stdout = grid_capture_redirector
            
            # Run the grid capture process with absolute path
            grid_capture = GridCapture(output_folder)
            grid_capture.capture_grid_cells()
            
            # Restore the original redirector
            sys.stdout = old_stdout
            
            self.safe_append_to_grid_creation_browser("Grid capture completed!")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "❌ Error", f"Failed to capture grid cells: {str(e)}")

    def on_start_process_clicked(self):
        """Main button logic"""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            self.on_generate_grid()
            self.on_capture_grid_clicked()

            input_folder = os.path.join(plugin_dir, "GridCaptures")
            output_folder = os.path.join(plugin_dir, "Classified_images")

            # Remove white pixels from captured images
            self.safe_append_to_grid_creation_browser("🔄 Removing white pixels from captured images...")

            for filename in os.listdir(input_folder):
                if filename.lower().endswith(".png"):
                    file_path = os.path.join(input_folder, filename)
                    try:
                        remover = WhitePixelRemover(input_path=file_path, output_path=file_path)
                        remover.process()
                        self.safe_append_to_grid_creation_browser(f"✅ Processed: {filename}")
                    except Exception as e:
                        self.safe_append_to_grid_creation_browser(f"❌ Failed to process {filename}: {str(e)}")

            self.safe_append_to_grid_creation_browser("✅ White pixel removal completed!")

            # Classify the cleaned images
            self.classifier = MismatchIdentifier(
                input_folder=input_folder,  # input_folder now has cleaned images
                output_folder=output_folder,
            )

            self.classifier.process_images()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "❌ Error", f"Process failed: {str(e)}")





    def closeEvent(self, event):
        """Clean up on close"""
        if self.classifier:
            try:
                self.classifier.log_signal.disconnect()
            except:
                pass
            self.classifier = None

        sys.stdout = self.stdout_backup
        sys.stderr = self.stderr_backup
        super(Mismatch_Identifier_PluginDialog, self).closeEvent(event)