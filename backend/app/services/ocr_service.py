import os
import cv2
import pytesseract
from PIL import Image


def extract_text_from_image(image_path: str) -> str:
    """
    Extracts text from an image using OpenCV preprocessing and Pytesseract.
    Based on Rohit's historical memorial/newspaper OCR pipeline.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at {image_path}")

    # For text files, read directly
    if image_path.lower().endswith((".txt", ".md", ".json")):
        with open(image_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    # Read image via OpenCV
    img = cv2.imread(image_path)
    if img is None:
        # Fallback to PIL Image reading if OpenCV imread returns None
        try:
            pil_img = Image.open(image_path)
            raw_text = pytesseract.image_to_string(pil_img)
            return raw_text.strip()
        except Exception as e:
            raise ValueError(f"Could not read image at {image_path}: {e}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Invert colors (useful for newspaper notices / white text on dark background)
    inverted = cv2.bitwise_not(gray)

    # Otsu thresholding
    thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # PSM 4: single column of variable sizes
    custom_config = r"--oem 3 --psm 4"
    raw_text = pytesseract.image_to_string(thresh, config=custom_config).strip()

    # If inverted threshold produced very little text, try standard grayscale thresholding
    if len(raw_text) < 10:
        thresh_std = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        raw_text_std = pytesseract.image_to_string(thresh_std, config=custom_config).strip()
        if len(raw_text_std) > len(raw_text):
            raw_text = raw_text_std

    # If still empty, try raw image directly
    if len(raw_text) < 5:
        raw_text = pytesseract.image_to_string(img).strip()

    return raw_text
