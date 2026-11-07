# Enter your own api key
# Enter the correct img path

# Method 2: Direct Image Processing (Gemini Vision)
Status: Highly Recommended
This method bypasses traditional OCR (Optical Character Recognition) entirely. Instead, it relies on the native multimodal "vision" capabilities of modern Large Language Models (LLMs) to read and reason about the image in a single step.
Libraries Used
google-generativeai: The official Google SDK to interact with the Gemini API.
Pydantic: A data validation library used to force the LLM to output perfect JSON matching a predefined schema.
PIL (Python Imaging Library): Used to load the image file into memory.
The Gemini Vision Workflow
Image Loading: The image is loaded using PIL's Image.open(image_path). No color correction, cropping, or thresholding is required.
Schema Definition: A Pydantic class (RelationshipData) is defined outlining the exact fields needed: subject, related_person, relationship_type, event, event_date, event_venue, and event_address.
Multimodal Prompting: Both the raw image and a text prompt are passed to the gemini-3.8-flash model simultaneously.
Structured Output: Using genai.GenerationConfig, the API is instructed to return application/json that strictly adheres to the RelationshipData schema.
Why this method is superior for newspapers:
Contextual Reading: It understands complex layouts (like multiple columns).
Color Independence: It natively reads inverted text (white text on black backgrounds), which is common in obituaries and causes traditional OCR to fail.
Zero Typos: It eliminates the "hallucinations" of traditional OCR (e.g., reading an "I" as a "1" or misreading faded text).
# Method 1: Traditional OCR Pipeline (Tesseract + OpenCV + LLM)
Status: Legacy / Alternative
This is a two-step approach. First, traditional Computer Vision techniques are used to clean the image and extract raw string text. Second, that raw text is fed into a text-only LLM for reasoning.
Libraries Used
cv2 (OpenCV): The industry standard for Computer Vision and image manipulation.
pytesseract: A Python wrapper for Google's Tesseract OCR engine.
numpy: Used under the hood by OpenCV for image matrix calculations.
google-generativeai & Pydantic: For the LLM reasoning phase.
Part 1: The Computer Vision & OCR Pipeline
Because Tesseract expects crisp, black text on a clean, white background, heavy preprocessing is required using OpenCV functions:
Image Loading: cv2.imread() loads the image as a multi-dimensional numpy array.
Grayscale Conversion: cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) removes color channels. Color confuses OCR engines.
Color Inversion (Crucial for Obituaries): cv2.bitwise_not() mathematically flips the pixel values. White pixels become black, and black pixels become white. This fixes the "white text on black background" issue.
Binarization: cv2.threshold(..., cv2.THRESH_BINARY + cv2.THRESH_OTSU) applies Otsu's method. This algorithm calculates the optimal threshold to force every single pixel to be strictly pure black or pure white, completely stripping away gray shadows, paper grain, or lighting gradients.
Text Extraction: pytesseract.image_to_string() runs the OCR engine.
Configuration Note: We use --psm 4 (Page Segmentation Mode 4), which assumes a single column of text of variable sizes, perfect for center-aligned memorial notices.
# LLM Reasoning
Text Prompting: The raw string output from Tesseract is injected into a text prompt.
Structuring: Just like Method 2, the gemini-3.8-flash model is asked to process the text, map out the relationships, fix any obvious OCR spelling mistakes, and output the data using the strict Pydantic JSON schema..

