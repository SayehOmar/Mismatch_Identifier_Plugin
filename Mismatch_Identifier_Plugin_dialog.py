import os
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtCore
from .GridCapture import GridCapture
from .File_loader import FileLoader
from .grid_filter import GridFilter
from .mismatch_identifier_Logic import MismatchIdentifier
from .stream_redirector import StreamRedirector
import sys


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "Mismatch_Identifier_Plugin_dialog_base.ui")
)

class Mismatch_Identifier_PluginDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(Mismatch_Identifier_PluginDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        
        # IMPORTANT: Wait until UI is fully set up before proceeding
        QtCore.QCoreApplication.processEvents()
        
        # This creates the widgets
        self.setupUi(self)

        # Save original stdout/stderr
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr

        # Redirect stdout to both console and QTextBrowser(s)
        # Now redirect stdout/stderr
        sys.stdout = self.output_capturer
        sys.stderr = self.error_capture

        # Store active classifiers
        self.classifiers = []
            

        
        # Connect signals AFTER UI is created
        self.output_capturer.text_written.connect(self.safe_append_to_grid_browser)
        self.error_capturer.text_written.connect(self.safe_append_to_image_browser)
        
        # Connect the Start Process button
        self.Start_Process.clicked.connect(self.on_start_process_clicked)

        # Create a FileLoader instance
        self.file_loader = FileLoader(self)

        # Connect the browse buttons from FileLoader to the current dialog
        self.Sauvegarde_Avant_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Avant_AI, 'folder1_path')
        )
        self.Sauvegarde_Apres_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Apres_AI, 'folder2_path')
        )
        self.Styles_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Styles, 'style_folder_path')
        )
        # Connect the Generate Grid button to the function that will create the grid
        self.Start_Process.clicked.connect(self.on_generate_grid)
        # Connect load button to load layers function
        self.StartLoading.clicked.connect(self.file_loader.load_layers)

    def append_to_processing_log(self, message):
        """Safely append text to the image processing browser"""
        if self.image_processing_browser:
            try:
                self.image_processing_browser.append(str(message))
            except RuntimeError:
                # Handle case where widget may have been deleted
                pass

    def on_generate_grid(self):
        """Callback for the Generate Grid button to generate grid."""
        plugin_dir = os.path.dirname(__file__)
        output_path = os.path.join(plugin_dir, "Grid", "grid.shp")
        reference_layer_name = "Arc_itineraire_AV"  # Name of the reference layer
        try:
            # Create a GridFilter instance
            grid_filter = GridFilter(reference_layer_name,output_path)

            # Select layer_by_name 
            grid_filter.get_layer_by_name()

            # generate_and_filter_grid
            grid_filter.generate_and_filter_grid()



            
            #QtWidgets.QMessageBox.information(self, "Success", "Grid generated and saved successfully!")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    
    def on_capture_grid_clicked(self):
        """Call the GridCapture class to capture grid cell images and metadata."""
        try:
            # Define the output folder (you can make this user-selectable)
            plugin_dir = os.path.dirname(__file__)
            output_folder = os.path.join(plugin_dir, "GridCaptures")

            # Instantiate GridCapture (no need for a path — it looks for 'Filtered_Grid' in QGIS)
            grid_capture = GridCapture(output_folder)
            
            # Run the capture
            grid_capture.capture_grid_cells()

           # QtWidgets.QMessageBox.information(self, "✅ Success", "Grid cell images and metadata exported!")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "❌ Error", f"Failed to capture grid cells: {str(e)}")

    
   
    def on_start_process_clicked(self):
        """Placeholder method for the Start Process button."""
        try:
        # Step 1: Generate and filter the grid
                self.on_generate_grid()

                # Step 2: Capture grid cell images and metadata
                self.on_capture_grid_clicked()

                # Final message (optional since substeps show messages too)
                classifier = MismatchIdentifier(
                        input_folder="GridCaptures",
                        output_folder="Classified_images",
                        logger=self.log_to_error_identifications  )
                
                
                
                
                 # Connect the log_signal to our safe append method
                self.classifier.log_signal.connect(self.append_to_processing_log)
                classifier.process_images()
                
                
                QtWidgets.QMessageBox.information(self, "Complete", "Full process completed successfully!")

        except Exception as e:
             QtWidgets.QMessageBox.critical(self, "❌ Error", f"Process failed: {str(e)}")        

    def closeEvent(self, event):
            """Handle cleanup when the dialog is closed."""
            # Disconnect signals to prevent deleted C++ object errors
            if self.classifier:
                try:
                    self.classifier.log_signal.disconnect()
                except:
                    pass
                self.classifier = None
                
            # Restore original stdout and stderr
            sys.stdout = self.stdout_backup
            sys.stderr = self.stderr_backup
            
            # Let the parent class handle the rest
            super(Mismatch_Identifier_PluginDialog, self).closeEvent(event)