from qgis.core import (QgsProject, QgsVectorLayer, QgsProcessingFeedback, 
                       QgsGeometry, QgsSpatialIndex, QgsFeature)
from qgis.analysis import QgsNativeAlgorithms
import processing

def select_layers_near_arc_itineraire(self, buffer_distance=10):
    """
    Select features from specified layers that intersect or are within a buffer 
    of Arc_itineraire layers.
    
    :param buffer_distance: Buffer distance in meters
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
        if 'Arc_itineraire' in layer.name()
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
        # Start editing mode
        target_layer.startEditing()
        
        # Clear previous selections
        target_layer.removeSelection()
        
        # Create a list to store selected feature IDs
        selected_feature_ids = []

        # Go through each Arc_itineraire layer
        for arc_layer in arc_layers:
            # Create a spatial index for faster processing
            index = QgsSpatialIndex()
            
            # Add buffered arc features to the spatial index
            for arc_feature in arc_layer.getFeatures():
                # Create a buffer around the arc line
                buffer_geom = arc_feature.geometry().buffer(buffer_distance, 5)
                
                # Add to spatial index
                index.addFeature(arc_feature)

                # Select features in target layer that intersect with buffer
                for target_feature in target_layer.getFeatures():
                    if buffer_geom.intersects(target_feature.geometry()):
                        selected_feature_ids.append(target_feature.id())

        # Select the features
        if selected_feature_ids:
            target_layer.selectByIds(list(set(selected_feature_ids)))
        
        # Commit changes
        target_layer.commitChanges()

        print(f"Selected {len(selected_feature_ids)} features in {target_layer.name()}")

    # Refresh the map canvas to show selections
    iface.mapCanvas().refreshAllLayers()