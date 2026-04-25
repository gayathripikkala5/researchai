# Deployment Guide

Recommended demo deployment:

- Backend: Render Web Service
- Frontend: Vercel, Netlify, or Render Static Site

## Backend on Render

1. Push this project to GitHub.
2. Open Render and create a new Web Service.
3. Select the GitHub repository.
4. Set the root directory to `backend`.
5. Use these commands:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

6. Add environment variable:

```text
CORS_ORIGINS=https://your-frontend-url.vercel.app
```

After deployment, copy the backend URL. It will look like:

```text
https://researchai-backend.onrender.com
```

## Frontend on Vercel

1. Import the same GitHub repository in Vercel.
2. Set the root directory to `frontend`.
3. Add environment variable:

```text
VITE_API_URL=https://your-backend-url.onrender.com
```

4. Deploy.

## Frontend on Netlify

1. Import the same GitHub repository in Netlify.
2. Set the base directory to `frontend`.
3. Build command: `npm ci && npm run build`
4. Publish directory: `frontend/dist`
5. Add environment variable:

```text
VITE_API_URL=https://your-backend-url.onrender.com
```

## Important

The backend uses SQLite and local file uploads. This is fine for a demo, but on many free hosts uploaded PDFs may disappear after the server restarts. The seeded demo papers will still come back automatically.
