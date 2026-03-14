import pytesseract
from PIL import Image
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\asmvd\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
def extract_text_from_image(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text
