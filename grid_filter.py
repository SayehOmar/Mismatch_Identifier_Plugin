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
import uuid
from qgis.core import QgsField
from qgis.PyQt.QtCore import QVariant
class GridGenerator:
    def __init__(self, reference_layer_name, grid_size=15, output_path="mismatch_identifier_plugin/Grid/grid.shp"):
        self.reference_layer_name = reference_layer_name
        if output_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(script_dir, "Grid", "grid.shp")
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
    def __init__(self, reference_layer_name,output_path="Grid/grid.shp"):
        self.reference_layer_name = reference_layer_name
        self.output_path=output_path
        self.reference_layer = self.get_layer_by_name(reference_layer_name)

    def get_layer_by_name(self, layer_name='Arc_itineraire_AV'):
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def generate_and_filter_grid(self, grid_size=10, buffer_distance=1, output_path="Grid/grid.shp"):
        """
        Generate a grid and filter it to only include cells that intersect with the reference layer.
        
        Parameters:
        - grid_size: Size of grid cells in map units
        - buffer_distance: Optional buffer distance around the reference layer (0 means no buffer)
        - output_path: Path to save the filtered grid
        
        Returns:
        - The filtered grid layer
        """
        print(f"Generating grid with cell size: {grid_size}...")
        if output_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(script_dir, "Grid", "grid.shp")
        # Get the reference layer extent, possibly with buffer
        extent = self.reference_layer.extent()
        if buffer_distance > 0:
            extent.grow(buffer_distance)
        
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
        
        # Create the grid layer
        grid_layer = QgsVectorLayer("Polygon?crs=" + self.reference_layer.crs().authid(), "Grid", "memory")
        provider = grid_layer.dataProvider()
        
        # Generate grid cells
        for x in range(int(xmin), int(xmax), grid_size):
            for y in range(int(ymin), int(ymax), grid_size):
                rect = QgsRectangle(x, y, x + grid_size, y + grid_size)
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromRect(rect))
                provider.addFeature(feature)
                
        print(f"Grid generated with {grid_layer.featureCount()} cells")
        
        # Get reference geometries, applying buffer if specified
        reference_geoms = []
        for feature in self.reference_layer.getFeatures():
            geom = feature.geometry()
            if buffer_distance > 0:
                geom = geom.buffer(buffer_distance, 5)
            reference_geoms.append(geom)
        
        # Create a filtered grid that only contains cells intersecting with the reference layer
        filtered_grid = QgsVectorLayer("Polygon?crs=" + grid_layer.crs().authid(), "Filtered_Grid", "memory")
        provider = filtered_grid.dataProvider()
        provider.addAttributes([QgsField("hex_id", QVariant.String)])
        filtered_grid.updateFields()
        # Add features that intersect with reference layer
        intersecting_features = []
        
        for grid_feature in grid_layer.getFeatures():
            grid_geom = grid_feature.geometry()
            if any(ref_geom.intersects(grid_geom) for ref_geom in reference_geoms):
                grid_feature.setFields(filtered_grid.fields())  # Ensure the fields match
                grid_feature.setAttribute("hex_id", uuid.uuid4().hex[:10])  # 10-char unique hex
                intersecting_features.append(grid_feature)
        
        provider.addFeatures(intersecting_features)
        print(f"Filtered grid contains {filtered_grid.featureCount()} cells that intersect with {self.reference_layer.name()}")
        
        # Create directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export the filtered grid
        result = QgsVectorFileWriter.writeAsVectorFormat(
            filtered_grid,
            output_path,
            "UTF-8",
            filtered_grid.crs(),
            "ESRI Shapefile"
        )

        # Parse the result
        if isinstance(result, tuple):
            error_code = result[0]
            error_message = result[1] if len(result) > 1 else ""
        else:
            error_code = result
            error_message = ""

        # Handle result based on error code
        if error_code == QgsVectorFileWriter.NoError:
            print(f"Filtered grid successfully exported to {output_path}")
            # Add the layer to QGIS project
            loaded_layer = QgsProject.instance().addMapLayer(filtered_grid.clone())
            print(f"Added filtered grid to QGIS project as layer: {loaded_layer.name()}")
            return filtered_grid
        else:
            print(f"Error exporting filtered grid: Code {error_code}, Message: {error_message}")
            return None