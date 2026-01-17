DocVault AI — Local Setup
1️⃣ Backend Setup

Open terminal in the backend folder:

cd backend


Create a Python virtual environment:

python -m venv .venv


Activate the virtual environment:

Windows:

.venv\Scripts\activate


Linux / Mac:

source .venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Create .env file by copying example:

copy .env.example .env


Run the backend server:

uvicorn app.main:app --reload


Verify backend is running by opening browser or using curl:

curl http://127.0.0.1:8000/health


Expected output:

{"status": "ok"}

2️⃣ Frontend Setup

Open terminal in the frontend folder:

cd frontend


Install frontend dependencies:

npm install


Create .env file if needed:

copy .env.example .env


Run the frontend dev server:

npm run dev


Open in browser:

http://localhost:5173/


Expected page display:

DocVault AI — Coming Soon
Backend status: ok

3️⃣ Smoke Test

Confirm backend /health endpoint returns JSON:

{"status":"ok"}


Confirm frontend page displays:

Backend status: ok


If both pass → environment setup is correct ✅

4️⃣ Notes

Backend must run before frontend, otherwise frontend fetch fails

.env files are used to configure environment variables (APP_NAME, ports, etc.)

All commands should work on a clean machine without extra configuration