import cv2
import numpy as np
import os
import shutil

class MismatchIdentifier:
    def __init__(self, input_folder="Output_images", output_folder="Classified_images"):
        self.input_folder = input_folder
        self.output_folder = output_folder

        # Define HSV color ranges
        self.color_ranges = {
            "green": ((35, 50, 50), (85, 255, 255)),
            "red1": ((0, 50, 50), (10, 255, 255)),
            "red2": ((170, 50, 50), (180, 255, 255)),
            "white": ((0, 0, 200), (180, 50, 255)),
        }

        # Create output folders
        self.categories = ["no_cartography_error", "please_check", "cartography_error", "random"]
        self._create_folders()

    def _create_folders(self):
        for category in self.categories:
            os.makedirs(os.path.join(self.output_folder, category), exist_ok=True)

    def _detect_colors(self, image):
        """Detects colors in an image and returns their pixel counts."""
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        detected_colors = {}

        for color, (lower, upper) in self.color_ranges.items():
            mask = cv2.inRange(hsv_image, np.array(lower), np.array(upper))
            detected_colors[color] = np.sum(mask > 0)

        # Combine both red masks
        detected_colors["red"] = detected_colors.pop("red1") + detected_colors.pop("red2")

        return detected_colors

    def calculate_pixels_per_meter(self):
        """Calculates the pixels per meter for the given image."""
        # Each cell is 20x20 meters, and the image is 3000x3000 pixels
        pixels_per_meter = 2000 / 10  # 150 pixels per meter
        return pixels_per_meter

    def classify_image(self, image_path):
        """Classifies an image into one of the predefined categories."""
        image = cv2.imread(image_path)
        if image is None:
            return None  # Skip invalid images

        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 1. Edge Detection
        edges = cv2.Canny(image, 50, 150)

        # 2. Color-Based Filtering
        green_mask = cv2.inRange(hsv_image, np.array(self.color_ranges["green"][0]), np.array(self.color_ranges["green"][1]))
        red_mask1 = cv2.inRange(hsv_image, np.array(self.color_ranges["red1"][0]), np.array(self.color_ranges["red1"][1]))
        red_mask2 = cv2.inRange(hsv_image, np.array(self.color_ranges["red2"][0]), np.array(self.color_ranges["red2"][1]))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        green_edges = cv2.bitwise_and(edges, edges, mask=green_mask)
        red_edges = cv2.bitwise_and(edges, edges, mask=red_mask)

        green_contours, _ = cv2.findContours(green_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        red_contours, _ = cv2.findContours(red_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        green_lines_present = np.sum(green_edges) > 0
        red_lines_present = np.sum(red_edges) > 0

        pixels_per_meter = self.calculate_pixels_per_meter()

        min_distance_meters = float('inf')
        for red_contour in red_contours:
            for green_contour in green_contours:
                # Calculate minimum distance between red_contour and green_contour
                distance_pixels = cv2.pointPolygonTest(green_contour, (int(red_contour[0][0][0]), int(red_contour[0][0][1])), True)
                distance_meters = abs(distance_pixels) / pixels_per_meter
                min_distance_meters = min(min_distance_meters, distance_meters)

        if min_distance_meters < 0.5 and green_lines_present and red_lines_present:
            return "please_check"
        elif green_lines_present and red_lines_present:
            return "cartography_error"
        elif green_lines_present and not red_lines_present:
            return "no_cartography_error"
        else:
            return "random"

    def process_images(self):
        """Processes all images in the input folder and classifies them."""
        for filename in os.listdir(self.input_folder):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue  # Skip non-image files

            image_path = os.path.join(self.input_folder, filename)
            category = self.classify_image(image_path)

            if category:
                destination = os.path.join(self.output_folder, category, filename)
                shutil.move(image_path, destination)
                print(f"Moved {filename} to {category}")

        print("✅ All images classified successfully!")

# Run the classifier
if __name__ == "__main__":
    classifier = MismatchIdentifier()
    classifier.process_images()