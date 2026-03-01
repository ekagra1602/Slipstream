import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LAMINAR_API_KEY = os.getenv("LAMINAR_API_KEY")
BROWSER_USE_API_KEY = os.getenv("BROWSER_USE_API_KEY")
