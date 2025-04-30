import os
import json
import time
import gc
import psutil
from PyQt5.QtCore import QSize, QCoreApplication
from PyQt5.QtGui import QImage, QPainter, QColor
from qgis.core import *
from qgis.utils import iface

class GridCaptureResume:
    def __init__(self, output_folder):
        self.output_folder = output_folder

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        self.grid_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Filtered_Grid" and isinstance(layer, QgsVectorLayer):
                self.grid_layer = layer
                break

        if not self.grid_layer:
            print("❌ Grid layer 'Filtered_Grid' not found.")
            return

        print(f"✅ Found grid layer: {self.grid_layer.name()}")

        layer_order = iface.mapCanvas().layers()
        self.other_layers = [
            layer for layer in layer_order
            if isinstance(layer, QgsVectorLayer) and layer.name() != "Filtered_Grid"
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

    def memory_stats(self):
        process = psutil.Process(os.getpid())
        used_mb = process.memory_info().rss / (1024 * 1024)
        free_mb = psutil.virtual_memory().available / (1024 * 1024)
        return round(used_mb, 2), round(free_mb, 2)

    def capture_remaining_cells(self):
        if not self.grid_layer:
            print("⚠️ No valid grid layer.")
            return

        grid_id_field_index = self.grid_layer.fields().indexOf('hex_id')
        if grid_id_field_index == -1:
            print("❌ Field 'hex_id' not found.")
            return

        # Scan for already captured images
        existing_images = set()
        for file in os.listdir(self.output_folder):
            if file.startswith("cell_") and file.endswith(".png"):
                grid_id = file.replace("cell_", "").replace(".png", "")
                existing_images.add(grid_id)

        total_features = self.grid_layer.featureCount()
        print(f"🔁 Resuming capture | Already done: {len(existing_images)} | Total grid cells: {total_features}")

        batch_size = 10
        processed_cells = 0
        new_cells = 0
        time_stamps = []
        start_time = time.time()
        last_update_time = start_time
        last_processed_time = start_time

        for feature in self.grid_layer.getFeatures():
            grid_cell_id = str(feature.attributes()[grid_id_field_index])
            if grid_cell_id in existing_images:
                continue

            new_cells += 1
            geom = feature.geometry()
            extent = geom.boundingBox()

            image_path = os.path.join(self.output_folder, f"cell_{grid_cell_id}.png")

            # Capture logic
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

            # Save metadata
            metadata = {
                "grid_id": grid_cell_id,
                "extent": {
                    "xmin": extent.xMinimum(),
                    "ymin": extent.yMinimum(),
                    "xmax": extent.xMaximum(),
                    "ymax": extent.yMaximum(),
                },
                "crs": self.grid_layer.crs().authid(),
                "layers": [layer.name() for layer in self.other_layers],
            }
            metadata_path = os.path.join(self.output_folder, f"cell_{grid_cell_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)

            processed_cells += 1
            if processed_cells <= 5:
                time_stamps.append(time.time() - start_time)

            if processed_cells % batch_size == 0:
                QCoreApplication.processEvents()
                before_gc = self.memory_stats()[0]
                gc.collect()
                after_gc = self.memory_stats()[0]
                recovered = round(before_gc - after_gc, 2)

            current_time = time.time()
            if current_time - last_update_time >= 300:
                used_mem, free_mem = self.memory_stats()
                if processed_cells >= 5:
                    avg_time = sum(time_stamps) / len(time_stamps)
                    remaining = total_features - len(existing_images) - processed_cells
                    eta_minutes = (remaining * avg_time) / 60
                    print(f"♻️ GC done | Recovered: {recovered} MB")
                    print(f"🕐 {processed_cells} new | ETA: {eta_minutes:.1f} min | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")
                else:
                    print(f"🕐 {processed_cells} new | Estimating ETA... | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")

                if current_time - last_processed_time >= 300:
                    print("⚠️ No cells processed in 5 min. Potential crash/hang.")
                last_update_time = current_time

            # Optional restart safety
            if processed_cells >= 8000:
                print("🛑 Processed 8000 cells, stopping to avoid crash. Please re-run to continue.")
                break

        print(f"✅ Resume complete. {processed_cells} new cells captured.")
