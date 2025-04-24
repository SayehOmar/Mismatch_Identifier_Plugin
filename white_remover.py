import cv2
import numpy as np

class WhitePixelRemover:
    def __init__(self, input_path, output_path, threshold=245):
        """
        :param input_path: str - path to the input PNG image.
        :param output_path: str - path to save the cleaned output image.
        :param threshold: int - pixel intensity above which pixels are considered white (default: 245).
        """
        self.input_path = input_path
        self.output_path = output_path
        self.threshold = threshold
        self.image = None
        self.result = None

    def load_image(self):
        """Load image and convert to RGBA."""
        self.image = cv2.imread(self.input_path)
        if self.image is None:
            raise FileNotFoundError(f"Image not found at {self.input_path}")
        self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2BGRA)

    def remove_white_pixels(self):
        """Set alpha to 0 for white pixels."""
        white_mask = np.all(self.image[:, :, :3] > self.threshold, axis=-1)
        self.image[white_mask] = [255, 255, 255, 0]
        self.result = self.image

    def save_image(self):
        """Save the modified image to the output path."""
        if self.result is not None:
            cv2.imwrite(self.output_path, self.result)
            print(f"Image saved to: {self.output_path}")
        else:
            raise ValueError("No result image to save.")

    def process(self):
        """Run the full pipeline."""
        self.load_image()
        self.remove_white_pixels()
        self.save_image()
