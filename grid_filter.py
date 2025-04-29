from qgis.core import (
    QgsProject, 
    QgsVectorLayer, 
    QgsFillSymbol, 
    QgsGeometry, 
    QgsFeature, 
    QgsRectangle, 
    QgsVectorFileWriter, 
    QgsSpatialIndex, 
    QgsFeatureRequest, 
    QgsField
)
from PyQt5.QtCore import QVariant
import os
import uuid

class GridFilter:
    def __init__(self, reference_layer_name, output_path="Grid/grid.shp"):
        self.reference_layer_name = reference_layer_name
        self.output_path = output_path
        self.reference_layer = self.get_layer_by_name(reference_layer_name)

    def get_layer_by_name(self, layer_name='Arc_itineraire_AV'):
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def create_spatial_index(self, layer):
        """Create a spatial index for the reference layer."""
        return QgsSpatialIndex(layer.getFeatures())

    def process_grid_batch(self, batch_features, reference_index, provider, grid_layer):
        intersecting_features = []
        for grid_feature in batch_features:
            grid_geom = grid_feature.geometry()
            grid_bbox = grid_geom.boundingBox()
            intersecting_ids = reference_index.intersects(grid_bbox)

            for feature_id in intersecting_ids:
                reference_feature = self.reference_layer.getFeature(feature_id)
                if reference_feature.geometry().intersects(grid_geom):
                    grid_feature.setFields(grid_layer.fields())
                    grid_feature.setAttribute("hex_id", uuid.uuid4().hex[:10])  # Unique 10-char hex
                    intersecting_features.append(grid_feature)

        provider.addFeatures(intersecting_features)

    def generate_and_filter_grid(self, grid_size=15, buffer_distance=1, output_path="Grid/grid.shp"):
        print(f"Generating grid with cell size: {grid_size}...")

        extent = self.reference_layer.extent()
        if buffer_distance > 0:
            extent.grow(buffer_distance)

        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()

        grid_layer = QgsVectorLayer("Polygon?crs=" + self.reference_layer.crs().authid(), "Grid", "memory")
        provider = grid_layer.dataProvider()

        # Add 'hex_id' field
        grid_layer.dataProvider().addAttributes([QgsField("hex_id", QVariant.String)])
        grid_layer.updateFields()

        reference_index = self.create_spatial_index(self.reference_layer)

        batch_features = []
        for x in range(int(xmin), int(xmax), grid_size):
            for y in range(int(ymin), int(ymax), grid_size):
                rect = QgsRectangle(x, y, x + grid_size, y + grid_size)
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromRect(rect))
                batch_features.append(feature)

                if len(batch_features) >= 1000:
                    self.process_grid_batch(batch_features, reference_index, provider, grid_layer)
                    batch_features = []

        if batch_features:
            self.process_grid_batch(batch_features, reference_index, provider, grid_layer)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save grid layer to disk
        QgsVectorFileWriter.writeAsVectorFormat(
            grid_layer, output_path, "UTF-8", grid_layer.crs(), "ESRI Shapefile"
        )
        print(f"Filtered grid successfully exported to {output_path}")

        # ✅ Add the exported layer to the project under the name "Filtered_Grid"
        added_layer = QgsVectorLayer(output_path, "Filtered_Grid", "ogr")
        if added_layer.isValid():
            QgsProject.instance().addMapLayer(added_layer)
            print("Filtered_Grid layer added to the project.")
        else:
            print("Failed to load the exported grid layer.")

        return added_layer
