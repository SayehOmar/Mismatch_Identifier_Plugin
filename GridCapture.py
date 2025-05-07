import os
import json
import time
import gc
import psutil
from PyQt5.QtCore import QSize, QCoreApplication
from PyQt5.QtGui import QImage, QPainter, QColor
from qgis.core import *
from qgis.utils import iface
import re

class GridCapture:
    def __init__(self, output_folder):
        self.output_folder = output_folder
        self.batch_capture_limit = 10000
        self.current_grid_part = 0
        self.total_cells_captured = 0

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        # Store the grid layers that are available in the project
        self.grid_layers = []
        self.find_grid_layers()
        
        if not self.grid_layers:
            print("❌ No grid layers found matching 'Filtered_Grid*'.")
            return

        print(f"✅ Found {len(self.grid_layers)} grid layer(s):")
        for i, layer in enumerate(self.grid_layers):
            print(f"   [{i+1}] {layer.name()} - {layer.featureCount()} cells")

        layer_order = iface.mapCanvas().layers()
        self.other_layers = [
            layer for layer in layer_order
            if isinstance(layer, QgsVectorLayer) and not layer.name().startswith("Filtered_Grid")
        ]

        print(f"✅ Found {len(self.other_layers)} other layers to render")

        self.map_settings = QgsMapSettings()
        self.map_settings.setLayers(self.other_layers)
        self.map_settings.setBackgroundColor(QColor(255, 255, 255))
        self.image_width = 650
        self.image_height = 650
        self.map_settings.setOutputSize(QSize(self.image_width, self.image_height))
        self.map_settings.setFlag(QgsMapSettings.Flag.Antialiasing, False)
        self.map_settings.setFlag(QgsMapSettings.Flag.UseAdvancedEffects, False)

        print("✅ Map settings initialized")
        
        # Create a progress log file
        self.log_path = os.path.join(self.output_folder, "capture_progress.txt")
        with open(self.log_path, "a") as log_file:
            log_file.write(f"=== New capture session started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    def find_grid_layers(self):
        """Find all grid layers matching the Filtered_Grid* pattern"""
        self.grid_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name().startswith("Filtered_Grid") and isinstance(layer, QgsVectorLayer):
                self.grid_layers.append(layer)
        
        # Sort the grid layers by part number if they have a pattern like "Filtered_Grid_Part1"
        def get_part_number(layer_name):
            match = re.search(r'Part(\d+)', layer_name)
            if match:
                return int(match.group(1))
            return 0  # Main grid has no part number
        
        self.grid_layers.sort(key=lambda layer: get_part_number(layer.name()))

    def memory_stats(self):
        process = psutil.Process(os.getpid())
        used_mb = process.memory_info().rss / (1024 * 1024)
        free_mb = psutil.virtual_memory().available / (1024 * 1024)
        return round(used_mb, 2), round(free_mb, 2)

    def load_next_grid_part(self):
        """Switch to the next grid part if available"""
        self.current_grid_part += 1
        if self.current_grid_part < len(self.grid_layers):
            print(f"🔄 Switching to next grid part: {self.grid_layers[self.current_grid_part].name()}")
            return True
        else:
            print("🏁 No more grid parts available. Processing complete.")
            return False

    def get_processed_cell_ids(self):
        """Get a set of already processed cell IDs to avoid reprocessing"""
        processed_ids = set()
        for filename in os.listdir(self.output_folder):
            if filename.startswith("cell_") and filename.endswith(".png"):
                processed_ids.add(filename[5:-4])  # Extract the hex_id part
        return processed_ids

    def capture_grid_cells(self):
        """Main function to process grid cells across multiple grid parts"""
        if not self.grid_layers:
            print("⚠️ No valid grid layers found.")
            return
        
        # Get already processed cells to avoid duplication
        processed_cell_ids = self.get_processed_cell_ids()
        print(f"📊 Found {len(processed_cell_ids)} already processed cells")
        
        start_time = time.time()
        total_captures = 0
        
        # Process each grid part one at a time
        while self.current_grid_part < len(self.grid_layers):
            current_grid = self.grid_layers[self.current_grid_part]
            part_name = current_grid.name()
            
            print(f"\n🔍 Processing grid part: {part_name}")
            processed_in_part = self._process_grid_part(current_grid, processed_cell_ids)
            
            total_captures += processed_in_part
            self.total_cells_captured += processed_in_part
            
            # Add summary to the log
            with open(self.log_path, "a") as log_file:
                log_file.write(f"\nCompleted {part_name}: {processed_in_part} cells captured\n")
                log_file.write(f"Total cells captured so far: {self.total_cells_captured}\n")
                log_file.write(f"Time elapsed: {(time.time() - start_time)/60:.2f} minutes\n")
            
            # Check if we should move to the next part
            if processed_in_part >= self.batch_capture_limit:
                print(f"🛑 Reached batch capture limit of {self.batch_capture_limit} cells for this part.")
                break
            elif not self.load_next_grid_part():
                break
        
        # Write final summary
        elapsed = time.time() - start_time
        summary = (
            f"\n=== Capture session completed at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
            f"Total processing time: {elapsed/60:.2f} minutes\n"
            f"Total cells captured: {self.total_cells_captured}\n"
            f"Grid parts processed: {self.current_grid_part + 1}/{len(self.grid_layers)}\n"
            f"Remaining grid parts: {len(self.grid_layers) - self.current_grid_part - 1}\n"
        )
        
        with open(self.log_path, "a") as log_file:
            log_file.write(summary)
        
        print("🎉 Grid cell capture process finished!")
        print(f"📄 Log file updated at: {self.log_path}")
        
        # Return information about progress for potential restart
        return {
            "completed": self.current_grid_part >= len(self.grid_layers),
            "total_captured": self.total_cells_captured,
            "next_part": self.current_grid_part + 1 if self.current_grid_part < len(self.grid_layers) else None,
            "remaining_parts": len(self.grid_layers) - self.current_grid_part - 1
        }

    def _process_grid_part(self, grid_layer, processed_cell_ids):
        """Process a single grid part"""
        hex_id_index = grid_layer.fields().indexOf('hex_id')
        
        # For sorting we'll use capture_count if available, otherwise just sort by feature ID
        capture_co_index = grid_layer.fields().indexOf('capture_count')
        
        if hex_id_index == -1:
            print(f"❌ Required field 'hex_id' not found in {grid_layer.name()}.")
            return 0

        # Get all features and sort them
        if capture_co_index != -1:
            print(f"Sorting features by 'capture_count'")
            features = sorted(grid_layer.getFeatures(), key=lambda f: f['capture_count'])
        else:
            print(f"No 'capture_count' field found, sorting by feature ID")
            features = list(grid_layer.getFeatures())
        
        total_features = len(features)
        print(f"🔍 Processing {total_features} grid cells from {grid_layer.name()}")

        batch_size = 10
        processed_cells = 0
        newly_captured_cells = 0  # Counter for new captures
        time_stamps = []
        start_time = time.time()
        last_update_time = start_time
        last_processed_time = start_time
        last_time_estimate = start_time
        last_capture_info = None
        
        # For time estimation
        remaining_to_process = total_features
        remaining_to_capture = min(self.batch_capture_limit, total_features - len(processed_cell_ids))

        for feature in features:
            geom = feature.geometry()
            extent = geom.boundingBox()
            hex_id = feature['hex_id']
            
            capture_co = feature['capture_count'] if capture_co_index != -1 else processed_cells
            last_capture_info = {
                'hex_id': hex_id,
                'capture_co': capture_co,
                'layer': grid_layer.name()
            }

            image_path = os.path.join(self.output_folder, f"cell_{hex_id}.png")
            
            # Skip if already processed
            if hex_id in processed_cell_ids or os.path.exists(image_path):
                processed_cells += 1
                continue

            # Check if we've reached the limit for this batch
            if newly_captured_cells >= self.batch_capture_limit:
                print(f"🛑 Reached batch capture limit of {self.batch_capture_limit} cells. Stopping this part.")
                break

            if processed_cells < 5:
                t0 = time.time()

            # Capture the cell
            self.map_settings.setExtent(extent)
            image = QImage(self.image_width, self.image_height, QImage.Format_RGB888)
            image.fill(QColor(255, 255, 255))
            painter = QPainter(image)

            map_renderer_job = QgsMapRendererParallelJob(self.map_settings)
            map_renderer_job.start()
            map_renderer_job.waitForFinished()

            rendered_image = map_renderer_job.renderedImage()
            painter.drawImage(0, 0, rendered_image)
            painter.end()
            image.save(image_path)
            newly_captured_cells += 1
            processed_cell_ids.add(hex_id)  # Mark as processed

            # Save metadata
            metadata = {
                "grid_id": hex_id,
                "capture_co": capture_co,
                "grid_layer": grid_layer.name(),
                "extent": {
                    "xmin": extent.xMinimum(),
                    "ymin": extent.yMinimum(),
                    "xmax": extent.xMaximum(),
                    "ymax": extent.yMaximum(),
                },
                "crs": grid_layer.crs().authid(),
                "layers": [layer.name() for layer in self.other_layers],
            }
            metadata_path = os.path.join(self.output_folder, f"cell_{hex_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)

            processed_cells += 1
            last_processed_time = time.time()

            if processed_cells <= 5:
                t1 = time.time()
                time_stamps.append(t1 - t0)

            # Periodic garbage collection
            if processed_cells % batch_size == 0:
                QCoreApplication.processEvents()
                before_gc = self.memory_stats()[0]
                gc.collect()
                after_gc = self.memory_stats()[0]
                recovered = round(before_gc - after_gc, 2)

            # Status updates and time estimation
            current_time = time.time()
            
            # More frequent time estimate updates (every 30 seconds)
            if current_time - last_time_estimate >= 30:
                if time_stamps and newly_captured_cells > 0:
                    # Calculate processing speed and remaining time
                    elapsed_time = current_time - start_time
                    avg_time_per_cell = elapsed_time / newly_captured_cells
                    
                    # Estimate remaining time for this batch
                    remaining_in_batch = min(self.batch_capture_limit - newly_captured_cells, 
                                             total_features - processed_cells)
                    batch_eta_minutes = (remaining_in_batch * avg_time_per_cell) / 60
                    
                    # Estimate time for all remaining cells across all grid parts
                    remaining_total = 0
                    for i in range(self.current_grid_part, len(self.grid_layers)):
                        if i == self.current_grid_part:
                            remaining_total += remaining_in_batch
                        else:
                            # Estimate for other grid parts
                            remaining_total += min(self.batch_capture_limit, self.grid_layers[i].featureCount())
                    
                    total_eta_minutes = (remaining_total * avg_time_per_cell) / 60
                    
                    # Update the timestamp of the last time estimate
                    last_time_estimate = current_time
                    
                    # Calculate projected finish times
                    batch_finish_time = time.strftime("%H:%M:%S", time.localtime(current_time + batch_eta_minutes * 60))
                    total_finish_time = time.strftime("%H:%M:%S", time.localtime(current_time + total_eta_minutes * 60))
                    
                    print(f"⏱️ Time estimate: Current batch will finish at {batch_finish_time} (in {batch_eta_minutes:.1f} min)")
                    print(f"⏱️ Total processing will finish at {total_finish_time} (in {total_eta_minutes:.1f} min)")
                    print(f"⏱️ Classification can start after batch completion")
                    
                    # Add to log file
                    with open(self.log_path, "a") as log_file:
                        log_file.write(f"Time estimate ({time.strftime('%H:%M:%S')}): " 
                                      f"Batch completion: {batch_finish_time}, "
                                      f"Total completion: {total_finish_time}\n")
            
            # Detailed status updates (every 5 minutes)
            if current_time - last_update_time >= 300:  # Every 5 minutes
                used_mem, free_mem = self.memory_stats()
                if time_stamps:
                    avg_time = sum(time_stamps) / len(time_stamps)
                    remaining = total_features - processed_cells
                    eta_minutes = (remaining * avg_time) / 60
                    print(f"♻️ Garbage collection done | Memory recovered: {recovered} MB")
                    print(f"🕐 {processed_cells}/{total_features} done ({newly_captured_cells} new) | ETA: {eta_minutes:.1f} min | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")
                    
                    # Update log file with progress
                    with open(self.log_path, "a") as log_file:
                        log_file.write(f"Progress update ({time.strftime('%H:%M:%S')}): {processed_cells}/{total_features} processed, {newly_captured_cells} new captures\n")
                else:
                    print(f"🕐 {processed_cells}/{total_features} done ({newly_captured_cells} new) | Estimating ETA... | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")

                if current_time - last_processed_time >= 300:
                    print("⚠️ No cells processed in the last 5 minutes. Potential crash or hang.")
                    
                last_update_time = current_time

        # Write part log entry
        elapsed = time.time() - start_time
        avg_time_per_cell = elapsed / newly_captured_cells if newly_captured_cells > 0 else 0
        
        part_log = (
            f"\n--- {grid_layer.name()} processing completed ---\n"
            f"Cells processed: {processed_cells}/{total_features}\n"
            f"New captures: {newly_captured_cells}\n"
            f"Time taken: {elapsed/60:.2f} minutes\n"
            f"Average time per cell: {avg_time_per_cell:.2f} seconds\n"
        )
        
        # Add estimates for next steps
        if self.current_grid_part < len(self.grid_layers) - 1:
            next_grid = self.grid_layers[self.current_grid_part + 1]
            next_size = next_grid.featureCount()
            est_time_next = min(self.batch_capture_limit, next_size) * avg_time_per_cell / 60
            part_log += f"Estimated time for next batch: {est_time_next:.2f} minutes\n"
        
        # Add estimate for when classification can start
        if newly_captured_cells == self.batch_capture_limit:
            part_log += f"Classification can start now for this batch of {newly_captured_cells} cells\n"
        elif newly_captured_cells > 0:
            part_log += f"Classification can start now for the {newly_captured_cells} captured cells\n"
        
        if last_capture_info:
            part_log += f"Last cell: hex_id={last_capture_info['hex_id']}, capture_co={last_capture_info['capture_co']}\n"
        
        with open(self.log_path, "a") as log_file:
            log_file.write(part_log)

        print(f"✅ Completed processing {grid_layer.name()}: {newly_captured_cells} new captures")
        
        # Add explicit message about when classification can start
        if newly_captured_cells > 0:
            print(f"🎯 Classification process can start now for the {newly_captured_cells} newly captured cells")
            print(f"   While the next batch is being processed in the background")
        
        return newly_captured_cells