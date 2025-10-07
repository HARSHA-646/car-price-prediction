"# car-price-prediction" 
# Car Price Prediction

## set up or create a environment
python -m venv (virturral env name)

## to activite environment
 (virtual env name)\Scripts\activate.bat

## Setup
pip install -r requirements.txt

## Run backend
uvicorn app.backend.app:app --reload --port 8000

## Frontend
open `frontend/index.html` or:
cd frontend
python -m http.server 8080

