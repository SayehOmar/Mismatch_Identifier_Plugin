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
    log_signal = pyqtSignal(str)
    classification_complete_signal = pyqtSignal(str, str, float)

    def __init__(self, input_folder="Output_images", output_folder="Classified_images", model_path=None):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.class_names = ["cartography_error", "no_cartography_error"]
        self.processed_files = set()
        self.is_watching = False

        self.model_path = model_path or os.path.join(os.path.dirname(__file__), "best_color_model.pth")

        self._create_folders()
        self.model = self._load_model()

        self.image_size = 224
        self.transforms = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        self.watcher = QFileSystemWatcher()
        self.watcher.directoryChanged.connect(self.on_directory_changed)

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_for_new_files)

        self.log("🔧 MismatchIdentifierLogic initialized")

    def log(self, message):
        try:
            self.log_signal.emit(str(message))
        except:
            pass
        print(message)

    def _create_folders(self):
        for category in self.class_names:
            os.makedirs(os.path.join(self.output_folder, category), exist_ok=True)

    def _load_model(self):
        try:
            model = ColorFocusedCNN(len(self.class_names))
            model.load_state_dict(torch.load(self.model_path, map_location=torch.device("cpu")))
            model.eval()
            return model
        except Exception as e:
            self.log(f"❌ Error loading model: {e}")
            return None

    def start_watching(self):
        if not self.is_watching:
            try:
                os.makedirs(self.input_folder, exist_ok=True)
                self.watcher.addPath(self.input_folder)
                self.scan_timer.start(2000)
                self.is_watching = True
                self.log(f"👀 Watching folder: {self.input_folder}")
                self.scan_for_new_files()
            except Exception as e:
                self.log(f"❌ Failed to start watching: {e}")

    def stop_watching(self):
        if self.is_watching:
            try:
                self.watcher.removePath(self.input_folder)
                self.scan_timer.stop()
                self.is_watching = False
                self.log(f"🛑 Stopped watching folder: {self.input_folder}")
            except Exception as e:
                self.log(f"❌ Error stopping watcher: {e}")

    def on_directory_changed(self, path):
        self.log(f"📁 Change detected: {path}")
        self.scan_for_new_files()

    def is_file_ready(self, path, wait_time=0.3):
        try:
            initial_size = os.stat(path).st_size
            time.sleep(wait_time)
            final_size = os.stat(path).st_size
            return initial_size == final_size
        except:
            return False

    def scan_for_new_files(self):
        if not os.path.exists(self.input_folder):
            return

        files = sorted(os.listdir(self.input_folder))
        for filename in files:
            if filename.lower().endswith((".png", ".jpg", ".jpeg")) and filename not in self.processed_files:
                image_path = os.path.join(self.input_folder, filename)
                if self.is_file_ready(image_path):
                    self.process_single_image(image_path)
                    self.processed_files.add(filename)

    def classify_image(self, image_path):
        try:
            if self.model is None:
                self.log("❌ Model not loaded.")
                return "random", {"reason": "Model not loaded."}

            image = Image.open(image_path).convert("RGB")
            image_tensor = self.transforms(image).unsqueeze(0)

            with torch.no_grad():
                output = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(output, dim=1)[0]
                confidence, predicted_class_index = torch.max(probabilities, 0)
                predicted_class_name = self.class_names[predicted_class_index.item()]
                confidence_score = confidence.item() * 100

            return predicted_class_name, {
                "confidence": confidence_score,
                "reason": f"Classified as {predicted_class_name} with {confidence_score:.2f}% confidence."
            }

        except Exception as e:
            self.log(f"❌ Classification error for {image_path}: {e}")
            return "random", {"reason": str(e)}

    def process_images(self):
        self.log("🚀 Starting real-time image classification...")
        self.start_watching()
        return {"status": "watching"}

    def process_single_image(self, image_path):
        try:
            filename = os.path.basename(image_path)
            category, report = self.classify_image(image_path)
            confidence = report.get("confidence", 0)

            dest_folder = os.path.join(self.output_folder, category)
            os.makedirs(dest_folder, exist_ok=True)
            dest_image_path = os.path.join(dest_folder, filename)
            shutil.move(image_path, dest_image_path)

            self.log(f"✅ '{filename}' ➡️ {category} ({confidence:.2f}%)")
            self.classification_complete_signal.emit(filename, category, confidence)

            json_filename = os.path.splitext(filename)[0] + ".json"
            json_path = os.path.join(self.input_folder, json_filename)
            dest_json_path = os.path.join(dest_folder, json_filename)

            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        data = json.load(f)
                    data["analysis_report"] = report
                    with open(dest_json_path, "w") as f:
                        json.dump(data, f, indent=4)
                    os.remove(json_path)
                except:
                    self.log("⚠️ Failed to read original JSON, writing only report.")
                    with open(dest_json_path, "w") as f:
                        json.dump({"analysis_report": report}, f, indent=4)
                    os.remove(json_path)
            else:
                with open(dest_json_path, "w") as f:
                    json.dump({"analysis_report": report}, f, indent=4)
                self.log("📝 Created new JSON report.")

        except Exception as e:
            self.log(f"❌ Failed to process {image_path}: {e}")
