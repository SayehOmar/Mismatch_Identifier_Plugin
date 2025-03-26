from qgis.core import (QgsProject, QgsVectorLayer, QgsGeometry, 
                       QgsSpatialIndex, QgsFeatureRequest)

def select_layers_near_arc_itineraire(buffer_distance=10):
    """
    Efficiently select features from specified layers that intersect 
    or are within a buffer of Arc_itineraire layers.
    
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
        # Start editing mode
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

            # Prepare a spatial request for efficiency
            request = QgsFeatureRequest()
            
            # Check intersections with buffered arcs
            for target_feature in target_layer.getFeatures():
                target_geom = target_feature.geometry()
                
                # Check if target feature intersects with any buffered arc
                if any(buffered_arc_geom.intersects(target_geom) for buffered_arc_geom in buffered_arc_geoms):
                    selected_feature_ids.add(target_feature.id())

        # Select the features
        if selected_feature_ids:
            target_layer.selectByIds(list(selected_feature_ids))
        
        # Commit changes
        target_layer.commitChanges()

        print(f"Selected {len(selected_feature_ids)} features in {target_layer.name()}")

    