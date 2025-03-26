from qgis.core import QgsProject, QgsVectorLayer, QgsFillSymbol, QgsGeometry, QgsFeature, QgsRectangle, QgsVectorFileWriter, QgsFeatureRequest
import os

class GridGenerator:
    def __init__(self, reference_layer_name, grid_size=20, output_path="Grid/grid.shp"):
        """
        Initialize the GridGenerator with the reference layer and grid size.

        Parameters:
        - reference_layer_name (str): The name of the reference layer to base the grid on (e.g., ROI).
        - grid_size (int): The size of the grid cells (default is 20 meters).
        - output_path (str): The path where the generated grid will be saved (default is "Grid/grid.shp").
        """
        self.reference_layer_name = reference_layer_name
        self.grid_size = grid_size
        self.output_path = output_path
        self.reference_layer = self.get_layer_by_name(reference_layer_name)

    def get_layer_by_name(self, layer_name):
        """Get the layer by name from the QGIS project."""
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  # If the layer exists, return the first one
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def generate_grid(self):
        """Generate a grid over the reference layer."""
        extent = self.reference_layer.extent()
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()

        # Create a new vector layer for the grid
        grid_layer = QgsVectorLayer("Polygon?crs=EPSG:27572", "Grid", "memory")
        provider = grid_layer.dataProvider()

        # Create grid cells
        for x in range(int(xmin), int(xmax), self.grid_size):
            for y in range(int(ymin), int(ymax), self.grid_size):
                # Define the grid cell as a rectangle
                rect = QgsRectangle(x, y, x + self.grid_size, y + self.grid_size)
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromRect(rect))
                provider.addFeature(feature)

        return grid_layer

    def save_grid(self):
        """Generate and save the grid to the specified output path."""
        grid_layer = self.generate_grid()

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Save the grid as a shapefile
        QgsVectorFileWriter.writeAsVectorFormat(
            grid_layer, self.output_path, "UTF-8", grid_layer.crs(), "ESRI Shapefile"
        )

        print(f"Grid saved to {self.output_path}")

class GridFilter:
    def __init__(self, reference_layer_name, buffer_distance=5, output_path="ROI/ROI.shp"):
        """
        Initialize the GridFilter with the reference layer and buffer distance.

        Parameters:
        - reference_layer_name (str): The name of the layer containing the reference feature (e.g., Arc_itineraire_AV).
        - buffer_distance (int): The distance within which to select other layers (default is 5 meters).
        """
        self.reference_layer_name = reference_layer_name
        self.buffer_distance = buffer_distance
        self.reference_layer = self.get_layer_by_name(reference_layer_name)
        self.selected_layers = []
        self.output_path = output_path
        self.roi_layer = None

    def get_layer_by_name(self, layer_name):
        """Get the layer by name from the QGIS project."""
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  # If the layer exists, return the first one
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")
        
    def create_roi_from_bbox(self):
        """Create a Region of Interest (ROI) from the bounding box of the reference layer."""
        # Get the extent (bounding box) of the reference layer
        extent = self.reference_layer.extent()

        # Create a new vector layer for the ROI
        self.roi_layer = QgsVectorLayer("Polygon?crs=EPSG:27572", "ROI", "memory")
        provider = self.roi_layer.dataProvider()

        # Create a feature with the geometry of the bounding box (extent)
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromRect(extent))
        provider.addFeature(feature)

        # Add the ROI layer to the project
        QgsProject.instance().addMapLayer(self.roi_layer)

        print("Region of Interest (ROI) created from bounding box.")

    def select_layers_near_arc_itineraire(buffer_distance=10):
        """
        Efficiently select features from specified layers that intersect 
        or are within a buffer of Arc_itineraire layers.
        
        :param buffer_distance: Buffer distance in meters (default is 10 meters)
        """
        # Target layers to select from
        target_layer_names = [
            'BD_PARCELLAIRE_batiment', 
            'BD_PARCELLAIRE_parcelle', 
            'Cadastre,_Polygone', 
            'Cadastre,_Polyligne'
        ]

        # Get all layers in the project
        project = QgsProject.instance()
        layers = project.mapLayers()

        # Find Arc_itineraire layers
        arc_layers = [
            layer for layer_id, layer in layers.items() 
            if 'Arc_itineraire_AV' in layer.name()
        ]

        if not arc_layers:
            print("No Arc_itineraire layers found.")
            return

        # Prepare target layers for selection
        target_layers = [
            layer for layer_id, layer in layers.items() 
            if any(name.lower() in layer.name().lower() for name in target_layer_names)
        ]

        if not target_layers:
            print("No target layers found.")
            return

        # Process each target layer
        for target_layer in target_layers:
            # Start editing mode for the target layer
            target_layer.startEditing()
            
            # Clear previous selections
            target_layer.removeSelection()
            
            # Create a set to store selected feature IDs for faster unique checking
            selected_feature_ids = set()

            # Go through each Arc_itineraire layer
            for arc_layer in arc_layers:
                # Collect all buffered arc geometries first
                buffered_arc_geoms = [
                    arc_feature.geometry().buffer(buffer_distance, 5) 
                    for arc_feature in arc_layer.getFeatures()
                ]

                # Prepare a spatial request for efficiency (optional here, since we're iterating manually)
                request = QgsFeatureRequest()

                # Go through each feature in the target layer
                for target_feature in target_layer.getFeatures():
                    target_geom = target_feature.geometry()
                    
                    # Check if the target feature intersects with any buffered arc geometry
                    if any(buffered_arc_geom.intersects(target_geom) for buffered_arc_geom in buffered_arc_geoms):
                        selected_feature_ids.add(target_feature.id())

            # Select the features
            if selected_feature_ids:
                target_layer.selectByIds(list(selected_feature_ids))
            
            # Commit changes
            target_layer.commitChanges()

            print(f"Selected {len(selected_feature_ids)} features in {target_layer.name()}")

        print("Selection process completed.")

        def apply_grid_filter(self):
            """Delete grid cells that don't intersect with selected features."""
            # Generate the grid
            grid_generator = GridGenerator(self.reference_layer_name)
            grid_layer = grid_generator.generate_grid()

            # Collect all the selected features from the selected layers
            selected_features = []
            for selected_layer in self.selected_layers:
                selected_features.extend([f for f in selected_layer.getFeatures()])

            # Filter out grid cells that don't intersect with the selected features
            provider = grid_layer.dataProvider()
            features_to_remove = []
            
            for grid_feature in grid_layer.getFeatures():
                grid_geom = grid_feature.geometry()
                intersects = False
                
                for selected_feature in selected_features:
                    if grid_geom.intersects(selected_feature.geometry()):
                        intersects = True
                        break
                
                if not intersects:
                    features_to_remove.append(grid_feature.id())

            # Remove the features that don't intersect
            grid_layer.dataProvider().deleteFeatures(features_to_remove)

            # Save the filtered grid
            grid_generator.save_grid()

            print("Filtered grid saved to", grid_generator.output_path)

    def apply_grid_separator(self):
        """Apply grid separator based on selected layers."""
        grid_generator = GridGenerator(self.reference_layer_name)
        grid_generator.save_grid()

    def select_layers_near_reference_layers(self, buffer_distance=10, reference_layer_names=None, target_layer_names=None):
        """
        Select features from target layers that intersect or are within a buffer of reference layers.
        
        :param buffer_distance: Buffer distance in meters
        :param reference_layer_names: List of reference layers' names (to create buffer zones)
        :param target_layer_names: List of target layers' names (from which features will be selected)
        """
        if reference_layer_names is None or target_layer_names is None:
            print("Please provide both reference and target layers.")
            return

        # Get all layers in the project
        project = QgsProject.instance()
        layers = project.mapLayers()

        # Find reference layers (those that will create the buffer)
        reference_layers = [
            layer for layer_id, layer in layers.items() 
            if any(name.lower() in layer.name().lower() for name in reference_layer_names)
        ]

        if not reference_layers:
            print("No reference layers found.")
            return

        # Find target layers (the layers to select from)
        target_layers = [
            layer for layer_id, layer in layers.items() 
            if any(name.lower() in layer.name().lower() for name in target_layer_names)
        ]

        if not target_layers:
            print("No target layers found.")
            return

        # Process each target layer
        for target_layer in target_layers:
            # Start editing mode
            target_layer.startEditing()
            
            # Clear previous selections
            target_layer.removeSelection()
            
            # Create a set to store selected feature IDs for faster unique checking
            selected_feature_ids = set()

            # Go through each reference layer
            for reference_layer in reference_layers:
                # Collect all buffered reference geometries first
                buffered_reference_geoms = [
                    reference_feature.geometry().buffer(buffer_distance, 5) 
                    for reference_feature in reference_layer.getFeatures()
                ]

                # Check each feature in the target layer
                for feature in target_layer.getFeatures():
                    feature_geom = feature.geometry()

                    # Check if the feature's geometry intersects with any buffered reference geometry
                    if any(buffered_geom.intersects(feature_geom) for buffered_geom in buffered_reference_geoms):
                        selected_feature_ids.add(feature.id())

            # Select the features that were found
            if selected_feature_ids:
                target_layer.select(selected_feature_ids)
            
            # Commit changes
            target_layer.commitChanges()

        print("Selection completed.")

    def export_selected_layers(self, export_dir="Exported_Layers"):
        """
        Export the selected layers to the specified directory.

        :param export_dir: Directory where selected layers will be exported (default is "Exported_Layers").
        """
        os.makedirs(export_dir, exist_ok=True)
        
        for idx, selected_layer in enumerate(self.selected_layers):
            layer_name = f"selected_layer_{idx + 1}.shp"
            export_path = os.path.join(export_dir, layer_name)
            
            # Export the selected layer to the specified path
            QgsVectorFileWriter.writeAsVectorFormat(
                selected_layer, export_path, "UTF-8", selected_layer.crs(), "ESRI Shapefile"
            )
            print(f"Exported selected layer {idx + 1} to {export_path}")

