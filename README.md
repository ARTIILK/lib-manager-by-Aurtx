BiblioFlow Web (FastAPI + React + Mongo/SQLite) with Optional Flask Local Backend

Overview
- Frontend: React + Tailwind (light teal #EDF7F6, dark blue-grey #2E4756, hover #3A5A6B, Segoe UI/Arial fallback)
- Backend (cloud): FastAPI with repository abstraction supporting MongoDB (default in cloud) or SQLite (local if MONGO_URL is absent)
- Optional Backend (local): Flask + SQLite in backend_flask/ with identical /api endpoints for offline simplicity

Live Preview
- URL: [Preview Link] (cloud uses FastAPI + MongoDB)

Run Locally (Option A – FastAPI + SQLite)
1) cd backend
2) Ensure MONGO_URL is NOT set in your environment
3) pip install -r requirements.txt
4) uvicorn server:app --host 0.0.0.0 --port 8001
   - Creates backend/students.db and backend/library.db automatically

Run Locally (Option B – Flask + SQLite)
1) cd backend_flask
2) pip install -r requirements.txt (Flask only)
3) python app.py  (binds 0.0.0.0:8001)
   - Creates backend_flask/app.db automatically

Frontend
1) cd frontend
2) yarn install
3) yarn start
- Uses frontend/.env REACT_APP_BACKEND_URL=/api

API Endpoints (same for FastAPI and Flask)
- GET /api/health
- Students: POST, GET, GET by id, PUT, DELETE at /api/students
- Books: POST, GET, GET /by-code/{code}, GET by id, PUT, DELETE at /api/books
- Borrow/Return: POST /api/borrow, POST /api/return, GET /api/borrows
- Suggestions: GET /api/suggest/students, GET /api/suggest/books

Validation & Rules
- admission_number must be exactly 6 characters (frontend + backend)
- SBIN or Stamp is required to create a book
- Cannot delete students or books with active borrows
- Overdue (>7 days) increments student warnings on return

Notes
- Cloud preview persists data in MongoDB
- Local runs can be SQLite without any external services