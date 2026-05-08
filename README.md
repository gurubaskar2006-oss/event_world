# Event World

Event World is a Chennai college event discovery platform for students and institutions. Students can discover events, save them, register, and view tickets. Institutions can submit events for review. Admins approve or reject submissions.

## Tech Stack

- Frontend: HTML, CSS, vanilla JavaScript
- Backend: FastAPI
- Database: MongoDB Atlas via Motor
- Auth: JWT with bcrypt password hashing
- Storage fallback: localStorage through `event-data.js`

## Run Locally

From the project root:

```powershell
cd backend
copy .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

If you do not have a virtual environment yet:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

## Environment Variables

Create `backend/.env` from `backend/.env.example`:

```env
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/eventworld
MONGO_DB=eventworld
JWT_SECRET=your_secret_key_here
JWT_DAYS=7
```

Use a real MongoDB Atlas connection string before relying on backend persistence.

## Deploy To Render

1. Push this project to GitHub.
2. Create a new Render Blueprint or Web Service.
3. Render can use `render.yaml`.
4. Add these environment variables in Render:
   - `MONGO_URL`
   - `JWT_SECRET`
5. Deploy.

The backend start command is:

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Admin Portal

Open:

```text
/admin-login.html
```

Demo admin credentials:

```text
Email: admin@eventworld.in
Password: EW@Admin2026!
```
