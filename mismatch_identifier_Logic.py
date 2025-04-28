import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import os
import shutil
import json
import time
from PyQt5.QtCore import QObject, pyqtSignal, QFileSystemWatcher, QTimer


class ColorFocusedCNN(nn.Module):
    def __init__(self, num_classes):
        super(ColorFocusedCNN, self).__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.color_attention = nn.Sequential(
            nn.Conv2d(128, 128, kernel_size=1), nn.BatchNorm2d(128), nn.Sigmoid()
        )
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        attention = self.color_attention(x)
        x = x * attention
        x = self.gap(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)
        return x


class MismatchIdentifierLogic(QObject):
    log_signal = pyqtSignal(str)  # Define a signal for logging
    classification_complete_signal = pyqtSignal(str, str, float)  # filename, category, confidence

    def __init__(self, input_folder="Output_images", output_folder="Classified_images", model_path=None):
        """
        Initialize the MismatchIdentifierLogic class.
        
        Args:
            input_folder (str): Directory containing images to process. Default is "Output_images".
            output_folder (str): Base directory for output folders. Default is "Classified_images".
            model_path (str, optional): Path to the model file. If None, uses 'best_color_model.pth' in the current directory.
        """
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.class_names = ["cartography_error", "no_cartography_error"]
        self.processed_files = set()  # Keep track of processed files
        self.is_watching = False
        
        # Set model path
        if model_path is None:
            self.model_path = os.path.join(os.path.dirname(__file__), "best_color_model.pth")
        else:
            self.model_path = model_path
        
        # Create output directories if they don't exist
        self._create_folders()
        
        # Load model
        self.model = self._load_model()
        
        # Set up image transformations
        self.image_size = 224
        self.transforms = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        
        # Initialize file watcher
        self.watcher = QFileSystemWatcher()
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        
        # Timer for periodic scans (as a backup to the watcher)
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_for_new_files)
        
        self.log("MismatchIdentifierLogic initialized")

    def log(self, message):
        """Log a message both via signal and to console"""
        # IMPORTANT: First emit the signal, then print
        try:
            self.log_signal.emit(str(message))
        except:
            pass  # Ignore errors with signal emission

        # Then print if needed
        print(message)

    def _create_folders(self):
        """Create output folders for each class"""
        for category in self.class_names:
            os.makedirs(os.path.join(self.output_folder, category), exist_ok=True)

    def _load_model(self):
        """Load the PyTorch model."""
        try:
            model = ColorFocusedCNN(len(self.class_names))
            model.load_state_dict(torch.load(self.model_path, map_location=torch.device("cpu")))
            model.eval()
            return model
        except Exception as e:
            self.log(f"Error loading model: {e}")
            return None
    
    def start_watching(self):
        """Start watching the input folder for new images"""
        if not self.is_watching:
            try:
                # Ensure folder exists before watching
                os.makedirs(self.input_folder, exist_ok=True)
                
                # Add the folder to the watcher
                self.watcher.addPath(self.input_folder)
                
                # Start the backup timer (scan every 2 seconds)
                self.scan_timer.start(2000)
                
                self.is_watching = True
                self.log(f"🔍 Started watching folder: {self.input_folder}")
                
                # Process any existing files
                self.scan_for_new_files()
                
            except Exception as e:
                self.log(f"Error starting watcher: {e}")
    
    def stop_watching(self):
        """Stop watching the input folder"""
        if self.is_watching:
            try:
                self.watcher.removePath(self.input_folder)
                self.scan_timer.stop()
                self.is_watching = False
                self.log(f"Stopped watching folder: {self.input_folder}")
            except Exception as e:
                self.log(f"Error stopping watcher: {e}")
    
    def on_directory_changed(self, path):
        """Called when the directory changes (new files added)"""
        self.log(f"Directory change detected in: {path}")
        self.scan_for_new_files()
    
    def scan_for_new_files(self):
        """Scan for new files in the input folder"""
        if not os.path.exists(self.input_folder):
            return
            
        for filename in os.listdir(self.input_folder):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")) and filename not in self.processed_files:
                image_path = os.path.join(self.input_folder, filename)
                
                # Check if file is ready/complete by testing if we can open it
                try:
                    with open(image_path, "rb") as f:
                        pass
                    
                    # Small delay to ensure file is completely written
                    time.sleep(0.1)
                    
                    # Process the file
                    self.process_single_image(image_path)
                    self.processed_files.add(filename)
                except:
                    # File is probably still being written
                    pass
    
    def classify_image(self, image_path):
        """
        Classify an image using the ML model.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            tuple: (predicted_class_name, report dictionary with confidence and other details)
        """
        try:
            # Check if model is loaded
            if self.model is None:
                self.log("Model not loaded. Please initialize the class properly.")
                return "random", {"reason": "Model not loaded properly."}
                
            # Load and preprocess the image
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.transforms(image).unsqueeze(0)  # Add batch dimension
            
            # Make the prediction
            with torch.no_grad():
                output = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(output, dim=1)[0]
                confidence, predicted_class_index = torch.max(probabilities, 0)
                predicted_class_name = self.class_names[predicted_class_index.item()]
                confidence_score = confidence.item() * 100
            
            # Create report dictionary
            report = {
                "confidence": confidence_score,
                "reason": f"ML model classified as {predicted_class_name} with {confidence_score:.2f}% confidence."
            }
                
            return predicted_class_name, report
            
        except FileNotFoundError:
            self.log(f"Error: Image file not found - {image_path}")
            return "random", {"reason": "Could not read image - file not found."}
        except Exception as e:
            self.log(f"An error occurred while classifying {image_path}: {e}")
            return "random", {"reason": f"Error during classification: {str(e)}"}

    def process_images(self):
        """
        Start the real-time processing of images in the input folder.
        This method now starts the watcher instead of processing all at once.
        """
        self.log("🔍 Starting real-time image classification...")
        self.start_watching()
        return {"status": "watching"}

    def process_single_image(self, image_path):
        """
        Process a single image and its corresponding JSON file.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            tuple: (predicted_class_name, confidence_score, destination_path) 
                  or (None, None, None) if an error occurs.
        """
        try:
            filename = os.path.basename(image_path)
            category, report = self.classify_image(image_path)
            confidence = report.get('confidence', 0)
            
            # Define destination paths
            destination_folder = os.path.join(self.output_folder, category)
            os.makedirs(destination_folder, exist_ok=True)
            dest_image_path = os.path.join(destination_folder, filename)
            
            # Move the image file
            shutil.move(image_path, dest_image_path)
            self.log(f"Image '{filename}' classified as: {category} with {confidence:.2f}% confidence")
            
            # Process corresponding JSON file
            json_filename = os.path.splitext(filename)[0] + ".json"
            json_path = os.path.join(self.input_folder, json_filename)
            dest_json_path = os.path.join(destination_folder, json_filename)
            
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r') as f:
                        existing_data = json.load(f)
                    existing_data["analysis_report"] = report
                    with open(dest_json_path, 'w') as f:
                        json.dump(existing_data, f, indent=4)
                    self.log(f"Updated and moved JSON to {category} folder")
                    os.remove(json_path)  # Remove original JSON after processing
                except json.JSONDecodeError:
                    self.log(f"Error decoding JSON. Creating new report file.")
                    with open(dest_json_path, 'w') as f:
                        json.dump({"analysis_report": report}, f, indent=4)
                    os.remove(json_path)  # Remove original JSON after processing
            else:
                self.log(f"No JSON found for {filename}. Creating new report file.")
                with open(dest_json_path, 'w') as f:
                    json.dump({"analysis_report": report}, f, indent=4)
            
            # Emit signal for other components to respond to
            self.classification_complete_signal.emit(filename, category, confidence)
            
            return category, confidence, dest_image_path
            
        except Exception as e:
            self.log(f"Error processing image {image_path}: {e}")
            return None, None, None


# Example usage if this file is run directly
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Create an instance of the classifier
    identifier = MismatchIdentifierLogic(
        input_folder="Output_images",
        output_folder="Classified_images"
    )
    
    # Connect to log signal for console output
    identifier.log_signal.connect(print)
    
    # Start watching for images
    identifier.process_images()
    
    # Run the event loop to process file events
    sys.exit(app.exec_())