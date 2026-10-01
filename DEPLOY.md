# Deploy PropKeep (Render)

This project is ready for **Render** (free tier works for a demo).

## What was prepared

- Env-based `config/settings.py` (`DEBUG`, `SECRET_KEY`, `DATABASE_URL`, hosts)
- `gunicorn` + `whitenoise` for static files
- Postgres via `DATABASE_URL` / `dj-database-url`
- `Procfile`, `build.sh`, `render.yaml`

## Steps to go live

### 1. Put the code on GitHub

In the project folder:

```bash
git init
git add .
git commit -m "Prepare PropKeep for production deploy"
```

Create a new empty repo on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 2. Create the app on Render

1. Sign up at https://render.com (login with GitHub).
2. **New → Blueprint** and select this repo (uses `render.yaml`),  
   **or** **New → Web Service** and connect the repo manually.
3. Add a **PostgreSQL** database (free) and link `DATABASE_URL` to the web service.
4. Set environment variables on the web service:

| Variable | Value |
|----------|--------|
| `DEBUG` | `False` |
| `SECRET_KEY` | long random string (Render can generate) |
| `DATABASE_URL` | from the Postgres service |
| `ALLOWED_HOSTS` | your host, e.g. `propkeep.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://propkeep.onrender.com` |

5. Build command: `chmod +x build.sh && ./build.sh`  
   Start command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
6. Deploy. Open the public URL when it finishes.

### 3. Create your live admin

In Render → your service → **Shell**:

```bash
python manage.py createsuperuser
```

Then open `/admin/` and enable HRMS for owners under **Owner HRMS settings** or `/hrms/settings/`.

### Notes

- **SQLite is not used in production** — Render Postgres is.
- Uploaded **media files** on the free disk are temporary; for permanent photos later use S3 / Cloudflare R2.
- Local development is unchanged: `python manage.py runserver` still uses SQLite when `DATABASE_URL` is not set.
