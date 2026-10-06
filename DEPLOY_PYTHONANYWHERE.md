# Deploy PropKeep on PythonAnywhere (free Beginner account)

Repo: **https://github.com/narenthar0007/pro_keeper**

Uses **SQLite** (no paid Postgres). Data stays on PythonAnywhere’s disk — fine for demo and small use.

Your live URL will be:

**https://YOURUSERNAME.pythonanywhere.com**

Replace `YOURUSERNAME` with your PythonAnywhere login everywhere below.

---

## 1. Create account

1. Go to [https://www.pythonanywhere.com/registration/register/beginner/](https://www.pythonanywhere.com/registration/register/beginner/)
2. Sign up (free **Beginner** — no card required for basic hosting)
3. Note your username (e.g. `narenthar`)

---

## 2. Open a Bash console

1. Top menu → **Consoles**
2. **Bash** → start a console

---

## 3. Clone and install

Run (use **Python 3.12** — required for `django-unfold`; **3.10 will fail** on `pip install`):

```bash
cd ~
git clone https://github.com/narenthar0007/pro_keeper.git
cd pro_keeper
python3.12 --version
mkvirtualenv --python=/usr/bin/python3.12 prokeeper
pip install -r requirements-pythonanywhere.txt
```

If `/usr/bin/python3.12` is missing, try `which python3.12` or check **Web** → create app → which Python versions are offered. Use that same version for `mkvirtualenv`.

If you already created a **3.10** venv and install failed, recreate it:

```bash
rmvirtualenv prokeeper
mkvirtualenv --python=/usr/bin/python3.12 prokeeper
cd ~/pro_keeper
pip install -r requirements-pythonanywhere.txt
```

**Do not set `DATABASE_URL`** — the app uses `db.sqlite3` in the project folder.

Generate a secret key and keep it handy:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Initialize the database:

```bash
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py createsuperuser
```

---

## 4. Create the web app

1. Top menu → **Web**
2. **Add a new web app**
3. **Manual configuration** (not Django wizard — we already have the project)
4. **Python 3.12** (or 3.11 if 3.12 is unavailable on your account — then use 3.12 venv from Bash as above)

On the **Web** tab for your site:

| Setting | Value |
|--------|--------|
| **Virtualenv** | `/home/Narenthar/.virtualenvs/prokeeper` (use your exact username; yours is likely `Narenthar`) |
| **Code** | `/home/Narenthar/pro_keeper` |

Click the **WSGI configuration file** link (opens `/var/www/..._wsgi.py`).

**Delete** the file contents and paste from:

`deploy/pythonanywhere_wsgi.py.example`

in the repo — or copy from GitHub. Replace:

- `YOURUSERNAME` → your PA username (twice in paths and twice in hostnames)
- `REPLACE-WITH-A-LONG-RANDOM-SECRET-KEY` → the key you generated

Save the WSGI file.

---

## 5. Static and media files

Still on the **Web** tab, scroll to **Static files**:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOURUSERNAME/pro_keeper/staticfiles` |
| `/media/` | `/home/YOURUSERNAME/pro_keeper/media` |

---

## 6. Go live

1. On the **Web** tab, click the green **Reload** button for your web app
2. Open **https://YOURUSERNAME.pythonanywhere.com**
3. Admin: **https://YOURUSERNAME.pythonanywhere.com/admin/**
4. Enable HRMS for owners: staff **HRMS subscriptions** or `/hrms/settings/`

---

## 7. Update the app later

In a **Bash** console:

```bash
cd ~/pro_keeper
workon prokeeper
git pull origin main
pip install -r requirements-pythonanywhere.txt
python manage.py migrate
python manage.py collectstatic --no-input
```

Then **Web** → **Reload**.

### Mobile app API (`/api/mobile/`)

After `git pull`, run `migrate` so `authtoken` tables exist. Reload the web app, then open:

`https://YOURUSERNAME.pythonanywhere.com/api/mobile/options/`

You should see JSON (amenities, property types, etc.). If you get the PropKeep **404** page, the server code is still old — pull again and reload.

The Expo app in `mobile/` defaults to `https://narenthar.pythonanywhere.com` (see `mobile/app.json` → `extra.apiUrl`).

---

## Free tier limits (good to know)

- One web app, `YOURUSERNAME.pythonanywhere.com` only (no custom domain on free)
- Limited CPU; site may be slow if many users hit it at once
- Outbound email may be restricted — rent reminders might not send until you upgrade email
- SQLite is OK for demo; for heavy production you’d move to MySQL (PA paid) or external DB later

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| **502 / error loading** | **Web** → **Error log**; fix WSGI paths and virtualenv path |
| **DisallowedHost** | `ALLOWED_HOSTS` in WSGI must be `YOURUSERNAME.pythonanywhere.com` |
| **CSRF error on login** | Set `CSRF_TRUSTED_ORIGINS` to `https://YOURUSERNAME.pythonanywhere.com` |
| **Static CSS missing** | Re-run `collectstatic`; check **Static files** mapping |
| **Redirect loop** | Keep `SECURE_SSL_REDIRECT=False` in WSGI (already in the example) |
