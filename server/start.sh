#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Run the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
