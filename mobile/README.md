# PropKeep mobile (Expo)

Connects to your live Django backend at **[https://narenthar.pythonanywhere.com](https://narenthar.pythonanywhere.com)** via `/api/mobile/` (same data and roles as the website).

## 1. Backend must be deployed (PythonAnywhere)

In a **Bash** console on PythonAnywhere (`workon prokeeper`):

```bash
cd ~/pro_keeper
git pull origin main
pip install -r requirements-pythonanywhere.txt
python manage.py migrate
```

Then **Web** → **Reload**.

Quick check (should return JSON, not an HTML 404 page):

`https://narenthar.pythonanywhere.com/api/mobile/options/`

## 2. Install and run the app

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with **Expo Go** (or run `npx expo run:android` / `npx expo run:ios` for a dev build).

## 3. Build installable Android APK (no Expo Go)

On Windows, double-click **`build-android-apk.bat`** in this folder (or run the steps below).

1. `npm install`
2. First time: run **`eas-login.bat`**, then **`eas-init.bat`**
3. Run **`build-android-apk.bat`** — cloud build on Expo (~10–20 min). The script uploads your **local** `mobile` folder (`EAS_NO_VCS=1`). If you rely on git-only uploads, **commit** `package.json` / `package-lock.json` (must include `expo-constants`) before building.
4. Download the APK from the link in the terminal or [expo.dev](https://expo.dev) → your project → Builds

Manual command:

```bash
npm install
npm run eas:login
npm run eas:init
npm run build:apk
```

## 4. Server URL on login

The login screen defaults to:

**`https://narenthar.pythonanywhere.com`**

(no trailing slash)

| Scenario | Server URL |
|---|---|
| Test against live site (default) | `https://narenthar.pythonanywhere.com` |
| Local Django on PC | `http://127.0.0.1:8000` |
| Android emulator → PC | `http://10.0.2.2:8000` |
| Phone on same Wi‑Fi as PC | `http://YOUR-PC-LAN-IP:8000` |

Log in with the same owner / tenant / admin accounts as the website.

## 5. API paths used by the app

All requests go to `{Server URL}/api/mobile/...` — auth, listings, dashboard, properties, tenants, inbox, rent reminders, tenant portal, admin broadcast, etc.

## 6. What the app can do

Same access rules as the web app:

- Browse listings, send enquiry, request vacant property (tenant)
- Owner dashboard, properties, amenities (incl. Others), tenants, create login, vacate date
- Inbox, rent reminders, leads, buildings
- Tenant portal
- Admin broadcast to all / owners / tenants

