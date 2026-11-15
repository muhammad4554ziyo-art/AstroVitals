import os
import sys

# Add repository root to Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from web_server import app

# Vercel serverless function entrypoint
# app is exposed for WSGI
