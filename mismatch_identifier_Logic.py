import cv2
import numpy as np
import os
import shutil
import time
import json
from PyQt5.QtCore import QObject, pyqtSignal

class MismatchIdentifier(QObject):  # Inherit from QObject to use signals
    log_signal = pyqtSignal(str)  # Define a signal for logging

    def __init__(self, input_folder="Output_images", output_folder="Classified_images"):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        # Create output folders
        self.categories = ["no_cartography_error",  "cartography_error"]
        self._create_folders()

    def log(self, message):
        # IMPORTANT: First emit the signal, then print
        try:
            self.log_signal.emit(str(message))
        except:
            pass  # Ignore errors with signal emission

        # Then print if needed
        print(message)


    def _create_folders(self):
        for category in self.categories:
            os.makedirs(os.path.join(self.output_folder, category), exist_ok=True)

    def calculate_pixels_per_meter(self):
        """Calculates the pixels per meter for the given image."""
        pixels_per_meter = 2000 / 15
        return pixels_per_meter

    def check_overlap_proximity(self, mask1, mask2, distance_threshold):
        """
        Checks if every pixel in mask1 has at least one pixel of mask2 within a given radius.
        Returns True if all pixels in mask1 has at least one pixel of mask2 within distance_threshold.
        """
        # If either mask is empty, there can't be overlap
        if np.sum(mask1) == 0 or np.sum(mask2) == 0:
            return False

        # Dilate mask2 to create a region that includes all pixels within distance_threshold
        kernel = np.ones((2 * distance_threshold + 1, 2 * distance_threshold + 1), np.uint8)
        dilated_mask2 = cv2.dilate(mask2, kernel, iterations=1)

        # Find all pixels in mask1
        mask1_pixels = np.where(mask1 > 0)

        # Check if all pixels in mask1 have at least one pixel of mask2 within distance_threshold
        for y, x in zip(mask1_pixels[0], mask1_pixels[1]):
            # If the corresponding pixel in dilated_mask2 is 0, then there's no pixel of mask2 within distance_threshold
            if dilated_mask2[y, x] == 0:
                return False

        return True

    def calculate_min_distance_efficient(self, mask1, mask2):
        """Calculates an efficient minimum pixel distance between two masks using distance transform."""
        if np.sum(mask1) == 0 or np.sum(mask2) == 0:
            return float('inf')

        dist_transform1 = cv2.distanceTransform(255 - mask1, cv2.DIST_L2, 5)
        min_dist1 = np.min(dist_transform1[mask2 > 0]) if np.any(mask2 > 0) else float('inf')

        dist_transform2 = cv2.distanceTransform(255 - mask2, cv2.DIST_L2, 5)
        min_dist2 = np.min(dist_transform2[mask1 > 0]) if np.any(mask1 > 0) else float('inf')

        return min(min_dist1, min_dist2)

    def classify_image(self, image_path):
        """Classifies an image based on the final logic."""
        image = cv2.imread(image_path)
        if image is None:
            return "random", {"reason": "Could not read image."}

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Define color masks
        orange_mask = cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))
        blue_mask = cv2.inRange(hsv, np.array([110, 150, 150]), np.array([130, 255, 255]))
        red_mask = cv2.inRange(hsv, np.array([0, 150, 150]), np.array([10, 255, 255]))
        green_mask = cv2.inRange(hsv, np.array([50, 150, 150]), np.array([70, 255, 255]))

        # Check presence of colors - convert NumPy bool_ to Python bool
        green_present = bool(np.sum(green_mask) > 0)
        red_present = bool(np.sum(red_mask) > 0)
        blue_present = bool(np.sum(blue_mask) > 0)
        orange_present = bool(np.sum(orange_mask) > 0)
        
        report = {
            "green_present": green_present,
            "red_present": red_present, 
            "blue_present": blue_present,
            "orange_present": orange_present
        }

        # If no cables are present, classify as random
        if not (green_present or red_present):
            report["reason"] = "No cables (green or red) detected."
            return "random", report

        # Check overlaps - convert NumPy bool_ to Python bool
        cables_overlap = False
        buildings_overlap = False
        
        if green_present and red_present:
            cables_overlap = bool(self.check_overlap_proximity(red_mask, green_mask, 3))
        
        if blue_present and orange_present:
            buildings_overlap = bool(self.check_overlap_proximity(orange_mask, blue_mask, 3))
        
        report["cables_overlap"] = cables_overlap
        report["buildings_overlap"] = buildings_overlap

        # Cartography error cases
        if blue_present and orange_present and not buildings_overlap:
            report["reason"] = "Blue building is not covering orange building."
            return "cartography_error", report
        
        if green_present and red_present and cables_overlap and not buildings_overlap:
            report["reason"] = "Cables overlap but buildings don't overlap."
            return "cartography_error", report
        
        # No cartography error cases
        if green_present and red_present and cables_overlap and buildings_overlap:
            report["reason"] = "Cables overlap and buildings overlap correctly."
            return "no_cartography_error", report
        
        # For the second image case (only blue and green)
        if blue_present and green_present and not red_present and not orange_present:
            report["reason"] = "Only blue buildings and green cables present, properly aligned."
            return "no_cartography_error", report
        
        # Default: needs human verification
        report["reason"] = "Case not covered by defined rules."
        return "please_check", report
        
        


    def process_images(self):
        """Processes all images in the input folder and classifies them, moving JSON files."""
        self.log("🔍 Starting image classification with new logic (moving JSONs)...")

        for filename in os.listdir(self.input_folder):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue  # Skip non-image files

            image_path = os.path.join(self.input_folder, filename)
            category, report = self.classify_image(image_path)
            self.log(f"Image {filename} classified as: {category} - Reason: {report.get('reason', 'N/A')}, Building Distance: {report.get('building_distance_meters', 'N/A')}, Cable Overlap: {report.get('cable_overlap', 'N/A')}, Building Overlap: {report.get('building_overlap', 'N/A')}")

            destination_folder = os.path.join(self.output_folder, category)
            os.makedirs(destination_folder, exist_ok=True)
            image_destination = os.path.join(destination_folder, filename)
            shutil.move(image_path, image_destination)

            # Move the corresponding JSON file
            json_filename = filename.rsplit(".", 1)[0] + ".json"
            json_path = os.path.join(self.input_folder, json_filename)
            report_destination = os.path.join(destination_folder, json_filename)

            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r') as f:
                        existing_data = json.load(f)
                    existing_data["analysis_report"] = report
                    with open(report_destination, 'w') as f:
                        json.dump(existing_data, f, indent=4)
                    self.log(f"Moved and updated existing {json_filename} to {category} with analysis report.")
                    os.remove(json_path) # Remove original JSON after processing
                except json.JSONDecodeError:
                    self.log(f"Error decoding JSON file: {json_path}. Saving new report.")
                    with open(report_destination, 'w') as f:
                        json.dump({"analysis_report": report}, f, indent=4)
                    shutil.move(json_path, report_destination.replace(".json", "_original.json")) # Rename original
            else:
                with open(report_destination, 'w') as f:
                    json.dump({"analysis_report": report}, f, indent=4)
                self.log(f"Saved analysis report to {json_filename} in {category}.")

        self.log("✅ Image classification completed with new logic (JSONs moved).")