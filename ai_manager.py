import os
from google import genai

client = genai.Client()

response = client.models.generate_content(
    model='gemini-3.5-flash-lite',
    contents='Tell me about the history of slavery.',
)


print(response.text)