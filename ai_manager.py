import os
from google import genai
from PIL import Image

client = genai.Client()

image_path = "cow.jpg"
image = Image.open(image_path)

response = client.models.generate_content(
    model='gemini-3.5-flash-lite',
    contents=[image, "What is this image?"],
)


print(response.text)