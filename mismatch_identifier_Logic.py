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
        self.categories = ["no_cartography_error", "please_check", "cartography_error", "random"]
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
        # The image is 2000x2000 pixels based on a grid of 20x20 meters
        pixels_per_meter = 2000 / 20  # 100 pixels per meter
        return pixels_per_meter

    def classify_image(self, image_path):
        """Classifies an image based on fiber and parcel alignment."""
        image = cv2.imread(image_path)
        if image is None:
            return None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Define color masks based on provided information
        orange_mask = cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))  # Assuming #fea500 falls in this range
        blue_mask = cv2.inRange(hsv, np.array([110, 150, 150]), np.array([130, 255, 255]))  # Assuming #0400fe falls in this range
        red_mask = cv2.inRange(hsv, np.array([0, 150, 150]), np.array([10, 255, 255]))    # Assuming #ff0004 falls in this range
        green_mask = cv2.inRange(hsv, np.array([50, 150, 150]), np.array([70, 255, 255]))  # Assuming #18e845 falls in this range

        pixels_per_meter = self.calculate_pixels_per_meter()
        report = {}

        def compare_buildings(mask_old, mask_new):
            """Compares old (blue) and new (orange) buildings."""
            contours_old, _ = cv2.findContours(mask_old, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours_new, _ = cv2.findContours(mask_new, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            building_report = {}

            if not contours_old and not contours_new:
                building_report["reason"] = "No old or new buildings detected."
                return "random", building_report
            elif not contours_old and contours_new:
                building_report["reason"] = "New buildings detected, but no old buildings found."
                return "cartography_error", building_report
            elif contours_old and not contours_new:
                building_report["reason"] = "Old buildings detected, but no new buildings found."
                return "cartography_error", building_report
            else:
                # Check for overlap (blue covering orange)
                overlap = cv2.bitwise_and(mask_old, mask_new)
                if np.sum(overlap > 0) > 0:
                    building_report["reason"] = "Old and new buildings overlap (new on top)."
                    return "no_cartography_error", building_report

                # Calculate minimum distance between contours
                min_distance_meters = float(0.5)
                for old_contour in contours_old:
                    for new_contour in contours_new:
                        # Calculate the centroid of the new contour
                        M = cv2.moments(new_contour)
                        if M["m00"] != 0:
                            cX = int(M["m10"] / M["m00"])
                            cY = int(M["m01"] / M["m00"])
                            # Calculate the signed distance from the centroid of the new contour to the old contour
                            distance = cv2.pointPolygonTest(old_contour, (cX, cY), True)
                            distance_abs_meters = abs(distance) / pixels_per_meter
                            min_distance_meters = min(min_distance_meters, distance_abs_meters)

                building_report["min_distance_meters"] = f"{min_distance_meters:.2f}"
                if min_distance_meters < 0.5:
                    building_report["reason"] = f"Minimum distance between buildings is {min_distance_meters:.2f} meters (within tolerance)."
                    return "no_cartography_error", building_report
                elif 0.5 <= min_distance_meters < 0.7:
                    building_report["reason"] = f"Minimum distance between buildings is {min_distance_meters:.2f} meters (requires check)."
                    return "please_check", building_report
                else:
                    building_report["reason"] = f"Minimum distance between buildings is {min_distance_meters:.2f} meters (cartography error)."
                    return "cartography_error", building_report

        def compare_cables(mask_old, mask_new):
            """Compares old (green) and new (red) cables."""
            contours_old, _ = cv2.findContours(mask_old, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours_new, _ = cv2.findContours(mask_new, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cable_report = {}

            if not contours_old and not contours_new:
                cable_report["reason"] = "No old or new cables detected."
                return "random", cable_report
            elif not contours_old and contours_new:
                cable_report["reason"] = "New cables detected, but no old cables found."
                return "cartography_error", cable_report
            elif contours_old and not contours_new:
                cable_report["reason"] = "Old cables detected, but no new cables found."
                return "cartography_error", cable_report
            else:
                # Calculate minimum distance between contours
                min_distance_meters = float(0.5)
                for old_contour in contours_old:
                    for new_contour in contours_new:
                        # Calculate the centroid of the new contour
                        M = cv2.moments(new_contour)
                        if M["m00"] != 0:
                            cX = int(M["m10"] / M["m00"])
                            cY = int(M["m01"] / M["m00"])
                            # Calculate the signed distance from the centroid of the new contour to the old contour
                            distance = cv2.pointPolygonTest(old_contour, (cX, cY), True)
                            distance_abs_meters = abs(distance) / pixels_per_meter
                            min_distance_meters = min(min_distance_meters, distance_abs_meters)

                cable_report["min_distance_meters"] = f"{min_distance_meters:.2f}"
                if min_distance_meters < 0.5:
                    cable_report["reason"] = f"Minimum distance between cables is {min_distance_meters:.2f} meters (within tolerance)."
                    return "no_cartography_error", cable_report
                elif 0.5 <= min_distance_meters < 0.7:
                    cable_report["reason"] = f"Minimum distance between cables is {min_distance_meters:.2f} meters (requires check)."
                    return "please_check", cable_report
                else:
                    cable_report["reason"] = f"Minimum distance between cables is {min_distance_meters:.2f} meters (cartography error)."
                    return "cartography_error", cable_report

        parcel_result, parcel_report = compare_buildings(blue_mask, orange_mask)
        cable_result, cable_report = compare_cables(green_mask, red_mask)

        report["parcel_check"] = {"result": parcel_result, "details": parcel_report}
        report["cable_check"] = {"result": cable_result, "details": cable_report}

        self.log(f"Parcel check: {parcel_result} | Cable check: {cable_result}")

        score_map = {
            "no_cartography_error": 1,
            "please_check": 2,
            "cartography_error": 3,
            "random": 4
        }

        final_result = max(parcel_result, cable_result, key=lambda x: score_map[x])
        return final_result, report


    def process_images(self):
        """Processes all images in the input folder and classifies them, saving a report to JSON."""
        self.log("🔍 Starting image classification...")

        for filename in os.listdir(self.input_folder):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue  # Skip non-image files

            image_path = os.path.join(self.input_folder, filename)
            category, report = self.classify_image(image_path)
            if category:
                destination_folder = os.path.join(self.output_folder, category)
                os.makedirs(destination_folder, exist_ok=True)
                image_destination = os.path.join(destination_folder, filename)
                shutil.move(image_path, image_destination)
                self.log(f"Moved {filename} to {category}")

                # Save the report to a JSON file
                json_filename = filename.rsplit(".", 1)[0] + ".json"
                json_path = os.path.join(self.input_folder, json_filename)
                report_destination = os.path.join(destination_folder, json_filename)

                # Check if a JSON file with the same name exists in the input folder
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as f:
                            existing_data = json.load(f)
                        existing_data["analysis_report"] = report
                        with open(report_destination, 'w') as f:
                            json.dump(existing_data, f, indent=4)
                        self.log(f"Updated existing {json_filename} in {category} with analysis report.")
                        os.remove(json_path) # Remove the original JSON after processing
                    except json.JSONDecodeError:
                        self.log(f"Error decoding JSON file: {json_path}. Saving new report.")
                        with open(report_destination, 'w') as f:
                            json.dump({"analysis_report": report}, f, indent=4)
                        if os.path.exists(json_path):
                            shutil.move(json_path, report_destination.replace(".json", "_original.json")) # Rename original JSON
                else:
                    with open(report_destination, 'w') as f:
                        json.dump({"analysis_report": report}, f, indent=4)
                    self.log(f"Saved analysis report to {json_filename} in {category}.")

        self.log("✅ Image classification completed.")

if __name__ == "__main__":
    classifier = MismatchIdentifier()
    classifier.process_images()