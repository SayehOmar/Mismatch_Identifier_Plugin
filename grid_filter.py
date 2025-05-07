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
import math

class GridFilter:
    def __init__(self, reference_layer_name, output_path="Grid/grid.shp"):
        self.reference_layer_name = reference_layer_name
        self.output_path = output_path
        self.reference_layer = self.get_layer_by_name(reference_layer_name)
        self.max_cells_per_batch = 10000
        self.sub_grid_index = 0

    def get_layer_by_name(self, layer_name='Arc_itineraire_AV'):
        layer = QgsProject.instance().mapLayersByName(layer_name)
        if layer:
            return layer[0]  
        else:
            raise ValueError(f"Layer '{layer_name}' not found in QGIS.")

    def create_spatial_index(self, layer):
        """Create a spatial index for the reference layer."""
        return QgsSpatialIndex(layer.getFeatures())

    def process_grid_batch(self, batch_features, reference_index, provider, grid_layer, capture_count):
        intersecting_features = []
        for grid_feature in batch_features:
            grid_geom = grid_feature.geometry()
            grid_bbox = grid_geom.boundingBox()
            intersecting_ids = reference_index.intersects(grid_bbox)

            for feature_id in intersecting_ids:
                reference_feature = self.reference_layer.getFeature(feature_id)
                if reference_feature.geometry().intersects(grid_geom):
                    grid_feature.setFields(grid_layer.fields())
                    hex_id = uuid.uuid4().hex[:12]  # Unique 12-char hex
                    grid_feature.setAttribute("hex_id", hex_id)
                    grid_feature.setAttribute("capture_count", capture_count)  # Add incremented capture count
                    intersecting_features.append(grid_feature)

                    capture_count += 1

        provider.addFeatures(intersecting_features)
        return capture_count

    def estimate_grid_cell_count(self, extent, grid_size):
        """Estimate the number of grid cells that will be generated."""
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
        width = xmax - xmin
        height = ymax - ymin
        
        cols = math.ceil(width / grid_size)
        rows = math.ceil(height / grid_size)
        
        # Estimate the number of cells that will intersect with the reference layer
        # This is a rough estimate assuming ~50% intersection rate
        total_cells = cols * rows
        est_intersecting_cells = int(total_cells * 0.5)
        
        return est_intersecting_cells

    def split_extent_into_subgrids(self, extent, grid_size, estimated_cells):
        """Split the extent into multiple subgrids to keep each below the cell limit."""
        if estimated_cells <= self.max_cells_per_batch:
            return [extent]
        
        # Calculate how many divisions we need
        divisions = math.ceil(estimated_cells / self.max_cells_per_batch)
        
        # Try to create a roughly square division pattern
        div_x = math.ceil(math.sqrt(divisions))
        div_y = math.ceil(divisions / div_x)
        
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
        width = xmax - xmin
        height = ymax - ymin
        
        x_step = width / div_x
        y_step = height / div_y
        
        subgrids = []
        for i in range(div_x):
            for j in range(div_y):
                sub_xmin = xmin + (i * x_step)
                sub_ymin = ymin + (j * y_step)
                sub_xmax = sub_xmin + x_step
                sub_ymax = sub_ymin + y_step
                
                # Create a rectangle for this subgrid
                subgrid = QgsRectangle(sub_xmin, sub_ymin, sub_xmax, sub_ymax)
                subgrids.append(subgrid)
        
        print(f"Split extent into {len(subgrids)} subgrids to keep cell count under {self.max_cells_per_batch}")
        return subgrids

    def generate_and_filter_grid(self, grid_size=15, buffer_distance=1, output_path="Grid/grid.shp"):
        print(f"Generating grid with cell size: {grid_size}...")

        extent = self.reference_layer.extent()
        if buffer_distance > 0:
            extent.grow(buffer_distance)

        # Estimate the number of grid cells
        estimated_cells = self.estimate_grid_cell_count(extent, grid_size)
        print(f"Estimated total grid cells: {estimated_cells}")
        
        # Split the extent if necessary
        subgrids = self.split_extent_into_subgrids(extent, grid_size, estimated_cells)
        
        # Process each subgrid
        all_layers = []
        capture_count = 1  # Start from 1 for the first cell
        
        for i, subgrid_extent in enumerate(subgrids):
            self.sub_grid_index = i
            sub_output_path = output_path
            
            # If we have multiple subgrids, create separate files
            if len(subgrids) > 1:
                base_path, ext = os.path.splitext(output_path)
                sub_output_path = f"{base_path}_part{i+1}{ext}"
            
            print(f"Processing subgrid {i+1}/{len(subgrids)}")
            added_layer = self._process_subgrid(subgrid_extent, grid_size, sub_output_path, capture_count)
            
            # Update the capture count for the next subgrid
            if added_layer:
                feature_count = added_layer.featureCount()
                capture_count += feature_count
                all_layers.append(added_layer)
                print(f"Subgrid {i+1} added {feature_count} cells. Total cells so far: {capture_count-1}")
        
        # If we processed multiple subgrids, we might want to merge them
        # But for now, we'll just return the list of layers
        if len(all_layers) > 1:
            print(f"Created {len(all_layers)} separate grid layers with a total of {capture_count-1} cells")
        
        return all_layers[0] if all_layers else None

    def _process_subgrid(self, extent, grid_size, output_path, start_capture_count):
        """Process a single subgrid."""
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()

        grid_layer = QgsVectorLayer("Polygon?crs=" + self.reference_layer.crs().authid(), "Grid", "memory")
        provider = grid_layer.dataProvider()

        # Add 'hex_id' and 'capture_count' fields
        grid_layer.dataProvider().addAttributes([
            QgsField("hex_id", QVariant.String), 
            QgsField("capture_count", QVariant.Int),
            QgsField("subgrid_id", QVariant.Int)  # Add a field to track which subgrid this cell belongs to
        ])
        grid_layer.updateFields()

        reference_index = self.create_spatial_index(self.reference_layer)

        batch_features = []
        capture_count = start_capture_count  # Start from the provided count

        for x in range(int(xmin), int(xmax), grid_size):
            for y in range(int(ymin), int(ymax), grid_size):
                rect = QgsRectangle(x, y, x + grid_size, y + grid_size)
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromRect(rect))
                batch_features.append(feature)

                if len(batch_features) >= 1000:
                    capture_count = self.process_grid_batch(batch_features, reference_index, provider, grid_layer, capture_count)
                    batch_features = []

        if batch_features:
            capture_count = self.process_grid_batch(batch_features, reference_index, provider, grid_layer, capture_count)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save grid layer to disk
        QgsVectorFileWriter.writeAsVectorFormat(
            grid_layer, output_path, "UTF-8", grid_layer.crs(), "ESRI Shapefile"
        )
        print(f"Filtered grid successfully exported to {output_path}")

        # Add the exported layer to the project
        layer_name = "Filtered_Grid"
        if len(self.split_extent_into_subgrids(self.reference_layer.extent(), grid_size, 
                                               self.estimate_grid_cell_count(self.reference_layer.extent(), grid_size))) > 1:
            layer_name = f"Filtered_Grid_Part{self.sub_grid_index+1}"
            
        added_layer = QgsVectorLayer(output_path, layer_name, "ogr")
        if added_layer.isValid():
            QgsProject.instance().addMapLayer(added_layer)
            print(f"{layer_name} layer added to the project.")
        else:
            print("Failed to load the exported grid layer.")

        return added_layer