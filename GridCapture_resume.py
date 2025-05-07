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

        self.log_file = os.path.join(self.output_folder, "log.txt")
        self.start_from_capture_co = None
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    log_data = f.readline().strip()
                    if log_data.startswith("Last capture_co:"):
                        self.start_from_capture_co = log_data.split(":")[1].strip()
                        print(f"📄 Resuming from last capture_co: {self.start_from_capture_co}")
                    else:
                        print("⚠️ Could not parse 'Last capture_co' from log.txt. Starting from the beginning.")
            except Exception as e:
                print(f"⚠️ Could not read log.txt: {e}. Starting from the beginning.")

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

        hex_id_index = self.grid_layer.fields().indexOf('hex_id')
        capture_co_index = self.grid_layer.fields().indexOf('capture_co')

        if hex_id_index == -1 or capture_co_index == -1:
            print("❌ Required fields 'hex_id' or 'capture_co' not found.")
            return

        # Sort features by capture_co
        features = sorted(self.grid_layer.getFeatures(), key=lambda f: f['capture_co'])
        total_features = len(features)
        print(f"🔍 Processing {total_features} grid cells by 'capture_co'")

        existing_images = set()
        for file in os.listdir(self.output_folder):
            if file.startswith("cell_") and file.endswith(".png"):
                grid_id = file.replace("cell_", "").replace(".png", "")
                existing_images.add(grid_id)

        print(f"🔁 Resuming capture | Already done: {len(existing_images)} | Total grid cells: {total_features}")

        batch_size = 10
        processed_cells = 0
        new_cells = 0
        time_stamps = []
        start_time = time.time()
        last_update_time = start_time
        last_processed_time = start_time
        last_capture_co = None
        capture_limit = 8000
        started_resuming = False

        for feature in features:
            geom = feature.geometry()
            extent = geom.boundingBox()
            hex_id = feature['hex_id']
            capture_co = feature['capture_co']
            last_capture_co = capture_co

            image_path = os.path.join(self.output_folder, f"cell_{hex_id}.png")
            if os.path.exists(image_path):
                continue

            if self.start_from_capture_co and not started_resuming:
                if capture_co == self.start_from_capture_co:
                    started_resuming = True
                continue
            elif self.start_from_capture_co and started_resuming is False:
                # This should ideally not be reached, but as a safety:
                continue

            if new_cells >= capture_limit:
                print(f"🛑 Reached capture limit of {capture_limit} new cells. Stopping.")
                break

            if processed_cells < 5:
                t0 = time.time()

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
            new_cells += 1

            metadata = {
                "grid_id": hex_id,
                "capture_co": capture_co,
                "extent": {
                    "xmin": extent.xMinimum(),
                    "ymin": extent.yMinimum(),
                    "xmax": extent.xMaximum(),
                    "ymax": extent.yMaximum(),
                },
                "crs": self.grid_layer.crs().authid(),
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
                    print(f"🕐 {new_cells} new | ETA: {eta_minutes:.1f} min | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")
                else:
                    print(f"🕐 {new_cells} new | Estimating ETA... | 🧠 Used: {used_mem} MB | Free: {free_mem} MB")

                if current_time - last_processed_time >= 300:
                    print("⚠️ No cells processed in 5 min. Potential crash/hang.")
                last_update_time = current_time

        # Write log file with the last capture_co
        elapsed = time.time() - start_time
        eta_text = f"Last capture_co: {last_capture_co}\nElapsed time: {elapsed/60:.2f} minutes\n"
        log_path = os.path.join(self.output_folder, "log.txt")
        with open(log_path, "w") as log_file:
            log_file.write(eta_text)

        print(f"✅ Resume complete. {new_cells} new cells captured.")

# Example of how to run the script
if __name__ == '__main__':
    output_folder = "C:/Users/essayeh.omar_amaris/Desktop/recalage"
    capture_tool = GridCaptureResume(output_folder)
    if capture_tool.grid_layer:
        capture_tool.capture_remaining_cells()