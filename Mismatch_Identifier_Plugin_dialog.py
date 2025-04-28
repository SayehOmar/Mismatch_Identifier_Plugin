import os
import sys
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtCore

from .GridCapture import GridCapture
from .File_loader import FileLoader
from .grid_filter import GridFilter
from .mismatch_identifier_Logic import MismatchIdentifierLogic
from .stream_redirector import StreamRedirector
from .white_remover import WhitePixelRemover
from .RecalageProcessor import BatchRecalageProcessor

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
        self.output_capturer = StreamRedirector(self.stdout_backup)
        self.error_capturer = StreamRedirector(self.stderr_backup)

        # Redirect stdout/stderr
        sys.stdout = self.output_capturer
        sys.stderr = self.error_capturer

        # Find the QTextBrowser by its object name
        self.grid_creation_browser = self.findChild(QtWidgets.QTextBrowser, "GridCreation_ImagesCapturing")

        # Connect signals AFTER UI is created
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
        self.SaveDirButton.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.lineEdit_4, 'Output_folder_path')
        )

        # Connect actions
        self.Start_Process.clicked.connect(self.on_generate_grid)
        self.StartLoading.clicked.connect(self.file_loader.load_layers)

        # Initialize classifier as None (will be created when needed)
        self.classifier = None

    def safe_append_to_grid_creation_browser(self, message):
        if self.grid_creation_browser:
            try:
                self.grid_creation_browser.append(str(message))
                # Auto-scroll to the bottom
                scrollbar = self.grid_creation_browser.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except RuntimeError:
                pass

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

    def on_classification_complete(self, filename, category, confidence):
        """Handle when a classification is complete"""
        self.safe_append_to_grid_creation_browser(
            f"✅ Classification complete: '{filename}' → {category} ({confidence:.2f}%)"
        )

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
            grid_capture_redirector = StreamRedirector(self.stdout_backup, delay_ms=50)
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

    def setup_classifier(self):
        """Initialize and start the classifier"""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        input_folder = os.path.join(plugin_dir, "GridCaptures")
        output_folder = os.path.join(plugin_dir, "Classified_images")

        try:
            # Create classifier if not exists
            if self.classifier is None:
                self.classifier = MismatchIdentifierLogic(
                    input_folder=input_folder,
                    output_folder=output_folder,
                )
                # Connect signals
                self.classifier.log_signal.connect(self.safe_append_to_grid_creation_browser)
                self.classifier.classification_complete_signal.connect(self.on_classification_complete)
                
            # Start the classifier in watching mode
            self.classifier.process_images()
            self.safe_append_to_grid_creation_browser("🔍 Classifier is now watching for new images...")
            
        except Exception as e:
            self.safe_append_to_grid_creation_browser(f"❌ Error setting up classifier: {str(e)}")

    def on_start_process_clicked(self):
        """Main button logic"""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            input_folder = os.path.join(plugin_dir, "GridCaptures")
            
            
            
            # Generate grid and capture images
            self.on_generate_grid()
            self.on_capture_grid_clicked()

            # Set up white pixel removal process
            #self.safe_append_to_grid_creation_browser("🔄 Starting white pixel removal for captured images...")
            
            
            '''
            for filename in os.listdir(input_folder):
                if filename.lower().endswith(".png"):
                    file_path = os.path.join(input_folder, filename)
                    try:
                        # The classifier will automatically pick up and process these files
                        # as they are created/modified by the white pixel remover
                        remover = WhitePixelRemover(input_path=file_path, output_path=file_path)
                        remover.process()
                        self.safe_append_to_grid_creation_browser(f"✅ Processed white pixels: {filename}")
                    except Exception as e:
                        self.safe_append_to_grid_creation_browser(f"❌ Failed to process {filename}: {str(e)}")

            self.safe_append_to_grid_creation_browser("✅ White pixel removal completed!")
            self.safe_append_to_grid_creation_browser("🔍 Classification will continue in background...")
            ''' 

            # Set up and start the classifier FIRST before generating images
            self.setup_classifier()

            # Start the recalage process
            self.safe_append_to_grid_creation_browser("🔄 Starting recalage process...")

            try:
                json_folder = os.path.join(plugin_dir, "Classified_images", "cartography_error")
                #  Get output folder from the QLineEdit
                output_folder = self.lineEdit_4.text().strip()

                recalage_processor = BatchRecalageProcessor(json_folder=json_folder, output_folder=output_folder)
                recalage_processor.run()
                self.safe_append_to_grid_creation_browser("✅ Recalage process completed!")
            except Exception as e:
                self.safe_append_to_grid_creation_browser(f"❌ Failed during recalage processing: {str(e)}")



        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "❌ Error", f"Process failed: {str(e)}")

    def closeEvent(self, event):
        """Clean up on close"""
        if self.classifier:
            try:
                self.classifier.stop_watching()  # Stop the file watcher
                self.classifier.log_signal.disconnect()
                self.classifier.classification_complete_signal.disconnect()
            except:
                pass
            self.classifier = None

        sys.stdout = self.stdout_backup
        sys.stderr = self.stderr_backup
        super(Mismatch_Identifier_PluginDialog, self).closeEvent(event)