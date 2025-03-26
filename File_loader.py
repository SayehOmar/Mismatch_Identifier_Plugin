import os
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QFileDialog ,QApplication 
from PyQt5.QtCore import QTimer  # Added for progress updates
from qgis.core import QgsProject, QgsVectorLayer
from .progressBar import create_progress_bar_manager 

class FileLoader(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FileLoader, self).__init__(parent)
        uic.loadUi('Mismatch_Identifier_Plugin_dialog_base.ui', self)
        
        
        # Instance variables to store paths
        self.folder1_path = ""
        self.folder2_path = ""
        self.style_folder_path = ""
        progress_bar = parent.findChild(QtWidgets.QProgressBar, 'progressBar_1')
        self.progress_manager = create_progress_bar_manager(progress_bar)
        
        

    def open_file_dialog(self, line_edit, folder_type):
        """Open a file dialog to select a folder and set it in the specified QLineEdit."""
        options = QtWidgets.QFileDialog.Options()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            options=options,
        )
        if folder_path:
            print(f"Selected folder path: {folder_path}") 
            line_edit.setText(folder_path)
            setattr(self, folder_type, folder_path)

    def load_layers(self):
        """Loads specific shapefiles from the folders and applies the styles from the style folder."""
        # Reset progress bar
        self.progress_manager.reset()
        
        
        # Get list of files to load
        required_files = [
            "BD_PARCELLAIRE_batiment.shp",
            "BD_PARCELLAIRE_parcelle.shp",
            "Cadastre,_Polygone.shp",
            "Cadastre,_Polyligne.shp",
            "Arc_itineraire.shp"
        ]

        total_files = len(required_files) * 2  # Layers from two folders
        
        # Set the total number of files for progress tracking
        self.progress_manager.set_total(total_files)
        
        
        # Get the project's layer tree root
        root = QgsProject.instance().layerTreeRoot()

        # Remove existing groups if they exist
        for group in root.findGroups():
            if group.name() in ["Avant AI", "Apres AI"]:
                root.removeChildNode(group)

        # Create new groups
        avant_ai_group = root.addGroup("Avant AI")
        apres_ai_group = root.addGroup("Apres AI")

        # Track loaded files
        loaded_files = 0

        # Load from first folder
        loaded_files += self.load_shapefiles(
            self.folder1_path, 
            self.style_folder_path, 
            required_files, 
            group_name="Avant AI",
            is_first_folder=True,
            total_files=total_files,
            loaded_files=loaded_files
        )

        # Load from second folder
        loaded_files += self.load_shapefiles(
            self.folder2_path, 
            self.style_folder_path, 
            required_files, 
            group_name="Apres AI",
            is_first_folder=False,
            total_files=total_files,
            loaded_files=loaded_files
        )

        # Ensure progress bar reaches 100%
        self.progress_manager.complete()
        

        

    def load_shapefiles(self, folder_path, style_folder_path, required_files, group_name, is_first_folder=True, total_files=1, loaded_files=0):
        """Loads specific shapefiles from a folder and applies the styles from the style folder."""
        folder_path = os.path.normpath(folder_path)
        
        if not folder_path:
            return 0  # Skip if folder path is empty
        
        if not os.path.exists(folder_path):
            QtWidgets.QMessageBox.warning(self, "Error", f"Folder not found: {folder_path}")
            return 0

        # Get the project and layer tree root
        project = QgsProject.instance()
        root = project.layerTreeRoot()

        files_loaded_in_this_folder = 0

        for filename in os.listdir(folder_path):
            # Check if the file is in the required files list
            if filename.lower() in [f.lower() for f in required_files]:
                layer_path = os.path.join(folder_path, filename)
                layer = QgsVectorLayer(layer_path, filename, 'ogr')

                if layer.isValid():
                    # Custom renaming logic
                    if filename.lower() == "arc_itineraire.shp":
                        # Rename Arc_itineraire based on folder
                        new_layer_name = f"Arc_itineraire_{'AV' if is_first_folder else 'AP'}"
                        layer.setName(new_layer_name)

                    # Add layer to project
                    project.addMapLayer(layer, False)
                    
                    # Find the group and add the layer
                    group = root.findGroup(group_name)
                    if group:
                        group.addLayer(layer)
                    
                    print(f"Loaded layer: {layer.name()} in group: {group_name}")

                    # Apply the style if provided
                    if style_folder_path:
                        self.apply_style_from_folder(layer, style_folder_path)


                    # Update progress bar
                    self.progress_manager.update_progress()
                    
                    

                else:
                    QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load layer: {filename}")

        return files_loaded_in_this_folder

    def apply_style_from_folder(self, layer, style_folder_path):
        """Applies a style from the style folder to the layer, based on matching layer name."""
        try:
            layer_name = layer.name().lower()  # Use the potentially renamed layer name
            
            for style_filename in os.listdir(style_folder_path):
                # Remove extension for more flexible matching
                style_name = os.path.splitext(style_filename)[0].lower()
                
                # More flexible matching
                if (style_name == layer_name or 
                    layer_name in style_name or 
                    style_name in layer_name):
                    
                    style_filepath = os.path.join(style_folder_path, style_filename)
                    
                    # Try QML first, then SLD
                    if style_filename.lower().endswith(".qml"):
                        success = layer.loadNamedStyle(style_filepath)
                        if success:
                            print(f"Successfully applied QML style from {style_filepath} to {layer.name()}")
                            layer.triggerRepaint()
                            return True
                    
                    elif style_filename.lower().endswith(".sld"):
                        success = layer.loadSldStyle(style_filepath)
                        if success:
                            print(f"Successfully applied SLD style from {style_filepath} to {layer.name()}")
                            layer.triggerRepaint()
                            return True
            
            print(f"No matching style found for layer: {layer.name()}")
            return False
        
        except Exception as e:
            print(f"Error applying style to {layer.name()}: {str(e)}")
            return False