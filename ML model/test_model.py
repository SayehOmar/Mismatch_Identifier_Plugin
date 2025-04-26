import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image


# Define the CNN model (must match the architecture of your trained model)
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


def classify_image(image_path, model_path, class_names):
    """
    Classifies an image using the provided model.

    Args:
        image_path (str): Path to the image file.
        model_path (str): Path to the saved PyTorch model weights (.pth file).
        class_names (list): A list of class names corresponding to the model's output.

    Returns:
        tuple: A tuple containing the predicted class name (str) and the confidence score (float).
               Returns None, None if an error occurs.
    """
    try:
        # Load the model
        num_classes = len(class_names)
        model = ColorFocusedCNN(num_classes)
        model.load_state_dict(
            torch.load(model_path, map_location=torch.device("cpu"))
        )  # Load to CPU for simplicity
        model.eval()

        # Define the image transformations (must match the training transformations)
        image_size = 224  # Assuming this was your training image size
        val_transforms = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

        # Load and preprocess the image
        image = Image.open(image_path).convert("RGB")
        image_tensor = val_transforms(image).unsqueeze(0)  # Add batch dimension

        # Make the prediction
        with torch.no_grad():
            output = model(image_tensor)
            probabilities = torch.nn.functional.softmax(output, dim=1)[0]
            confidence, predicted_class_index = torch.max(probabilities, 0)
            predicted_class_name = class_names[predicted_class_index.item()]
            confidence_score = confidence.item() * 100

        return predicted_class_name, confidence_score

    except FileNotFoundError:
        print(f"Error: Image or model file not found.")
        return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None


if __name__ == "__main__":
    model_file = (
        "best_color_model.pth"  # Replace with the actual path to your saved model
    )
    class_labels = [
        "cartography_error",
        "no_cartography_error",
    ]  # Replace with your actual class names

    while True:
        image_file = input("Enter the path to the image file (or 'stop' to exit): ")
        if image_file.lower() == "stop":
            break

        predicted_class, confidence = classify_image(
            image_file, model_file, class_labels
        )

        if predicted_class:
            print(
                f"The image '{image_file}' is classified as: {predicted_class} with a confidence of {confidence:.2f}%"
            )
        else:
            print(
                f"Could not classify the image '{image_file}'. Please check the path and ensure the model and labels are correct."
            )

    print("Exiting the classification loop.")
