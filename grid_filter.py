from qgis.core import (
    QgsProject, 
    QgsVectorLayer, 
    QgsFillSymbol, 
    QgsGeometry, 
    QgsFeature, 
    QgsRectangle, 
    QgsVectorFileWriter, 
    QgsFeatureRequest,
    QgsCoordinateTransformContext, 
    QgsVectorLayer
)
import os

class GridGenerator:
    def __init__(self, reference_layer_name, grid_size=20, output_path="Grid/grid.shp"):
        self.reference_layer_name = reference_layer_name
        self.grid_size = grid_size
        self.output_path = output_path
        self.reference_layer = self.get_layer_by_name(reference_layer_name)

    def get_layer_by_name(self, layer_name):
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def generate_grid(self):
        extent = self.reference_layer.extent()
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()

        grid_layer = QgsVectorLayer("Polygon?crs=" + self.reference_layer.crs().authid(), "Grid", "memory")
        provider = grid_layer.dataProvider()

        for x in range(int(xmin), int(xmax), self.grid_size):
            for y in range(int(ymin), int(ymax), self.grid_size):
                rect = QgsRectangle(x, y, x + self.grid_size, y + self.grid_size)
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromRect(rect))
                provider.addFeature(feature)

        return grid_layer

    def save_grid(self):
        grid_layer = self.generate_grid()
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        QgsVectorFileWriter.writeAsVectorFormat(
            grid_layer, self.output_path, "UTF-8", grid_layer.crs(), "ESRI Shapefile"
        )
        print(f"Grid saved to {self.output_path}")
        return grid_layer


class GridFilter:
    def __init__(self, reference_layer_name, buffer_distance=5, output_path="ROI/ROI.shp"):
        self.reference_layer_name = reference_layer_name
        self.buffer_distance = buffer_distance
        self.reference_layer = self.get_layer_by_name(reference_layer_name)
        self.selected_layers = []
        self.output_path = output_path
        self.roi_layer = None
        self.selected_features = []  



    def create_roi_from_bbox(self):
        if not self.selected_features:
            print("No selected features available to create ROI.")
            return None

        roi_layer = QgsVectorLayer("Polygon?crs=" + self.reference_layer.crs().authid(), "ROI", "memory")
        provider = roi_layer.dataProvider()

        for geom in self.selected_features:
            feature = QgsFeature()
            feature.setGeometry(geom)  
            provider.addFeature(feature)

        self.roi_layer = roi_layer
        print("ROI layer created successfully.")
        return roi_layer
   

    def get_layer_by_name(self, layer_name):
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def select_layers_within_buffer(self, buffer_distance=None, reference_layer_names=None, target_layer_names=None):
        if buffer_distance is None:
            buffer_distance = self.buffer_distance

        if reference_layer_names is None:
            reference_layer_names = [self.reference_layer_name]

        if target_layer_names is None:
            target_layer_names = [
                'BD_PARCELLAIRE_batiment', 
                'BD_PARCELLAIRE_parcelle', 
                'Cadastre,_Polygone', 
                'Cadastre,_Polyligne'
            ]

        project = QgsProject.instance()
        layers = project.mapLayers()

        reference_layers = [
            layer for layer_id, layer in layers.items() 
            if any(name.lower() in layer.name().lower() for name in reference_layer_names)
        ]

        if not reference_layers:
            print("No reference layers found.")
            return

        target_layers = [
            layer for layer_id, layer in layers.items() 
            if any(name.lower() in layer.name().lower() for name in target_layer_names)
        ]

        if not target_layers:
            print("No target layers found.")
            return

        self.selected_layers = []
        self.selected_features = []  

        for target_layer in target_layers:
            target_layer.startEditing()
            target_layer.removeSelection()
            selected_feature_ids = set()

            for reference_layer in reference_layers:
                buffered_reference_geoms = [
                    reference_feature.geometry().buffer(buffer_distance, 5) 
                    for reference_feature in reference_layer.getFeatures()
                ]

                for feature in target_layer.getFeatures():
                    feature_geom = feature.geometry()

                    if any(buffered_geom.intersects(feature_geom) for buffered_geom in buffered_reference_geoms):
                        selected_feature_ids.add(feature.id())
                        self.selected_features.append(feature.geometry())  

            if selected_feature_ids:
                target_layer.selectByIds(list(selected_feature_ids))
            
            target_layer.commitChanges()

            if selected_feature_ids:
                self.selected_layers.append(target_layer)
                print(f"Selected {len(selected_feature_ids)} features in {target_layer.name()}")

        print("Selection completed.")

    def apply_grid_separator(self, grid_size=20, output_path="Grid/grid.shp"):
        grid_generator = GridGenerator(
            reference_layer_name=self.reference_layer_name, 
            grid_size=grid_size, 
            output_path=output_path
        )
        
        grid_layer = grid_generator.save_grid()
        print(f"Grid separator applied and saved to {output_path}")
        return grid_layer

    def filter_grid_by_selection(self, grid_layer):
        if not self.selected_features:
            print("No selected features to filter the grid.")
            return None

        filtered_grid = QgsVectorLayer("Polygon?crs=" + grid_layer.crs().authid(), "Filtered_Grid", "memory")
        provider = filtered_grid.dataProvider()

        for feature in grid_layer.getFeatures():
            grid_geom = feature.geometry()

            if any(selected_geom.intersects(grid_geom) for selected_geom in self.selected_features):
                provider.addFeature(feature)

        return filtered_grid
    
    
    def export_selected_layers(self, export_dir="Exported_Layers", filtered_grid=None):
        os.makedirs(export_dir, exist_ok=True)
        print("Contents of self.selected_layers:")
        for layer in self.selected_layers:
            print(f"  - {layer.name()}")

        for idx, selected_layer in enumerate(self.selected_layers):
            layer_name = f"selected_layer_{idx + 1}.shp"
            export_path = os.path.join(export_dir, layer_name)

            # Create a new layer containing only selected features
            selected_features = selected_layer.selectedFeatures()
            print(f"Number of selected features in {selected_layer.name()}: {len(selected_features)}")
            if not selected_features:
                print(f"No selected features in {selected_layer.name()}, skipping export.")
                continue
            # Create a new memory layer for the selected features
            selected_layer_filtered = QgsVectorLayer(
                selected_layer.source(), f"Selected_{selected_layer.name()}", "memory"
            )
            provider = selected_layer_filtered.dataProvider()
            provider.addFeatures(selected_features)

            # --- Use the new writeAsVectorFormatV3 method ---
            crs = selected_layer.crs()
            transform_context = QgsCoordinateTransformContext()
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.fileEncoding = "UTF-8"
            options.driverName = "ESRI Shapefile"

            # Initialize an error message variable
            error_message = ""
            
            # Corrected writeAsVectorFormatV3 call: passing 5 arguments
            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                selected_layer_filtered,
                export_path,
                transform_context,
                options,
                error_message
            )

            if error == QgsVectorFileWriter.NoError:
                print(f"Exported selected layer {idx + 1} to {export_path}")
            else:
                print(f"Error exporting selected layer {idx + 1}: {error_message}")
            # -----------------------------------------------

        if filtered_grid:
            grid_path = os.path.join(export_dir, "Filtered_Grid.shp")

            # --- Use the new writeAsVectorFormatV3 method for the grid as well ---
            crs_grid = filtered_grid.crs()
            transform_context_grid = QgsCoordinateTransformContext()
            options_grid = QgsVectorFileWriter.SaveVectorOptions()
            options_grid.fileEncoding = "UTF-8"
            options_grid.driverName = "ESRI Shapefile"

            error_message_grid = ""
            error_grid = QgsVectorFileWriter.writeAsVectorFormatV3(
                filtered_grid,
                grid_path,
                transform_context_grid,
                options_grid,
                error_message_grid
            )

            if error_grid == QgsVectorFileWriter.NoError:
                print(f"Filtered grid exported to {grid_path}")
            else:
                print(f"Error exporting filtered grid: {error_message_grid}")
