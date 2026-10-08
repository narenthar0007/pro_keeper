@echo off
cd /d "%~dp0"

echo ========================================
echo   PropKeep - Build Android APK
echo ========================================
echo.

if not exist "node_modules\" (
  echo Installing npm dependencies...
  call npm.cmd install
  if errorlevel 1 goto :fail
)

echo Checking JavaScript bundle...
call npm.cmd run verify:bundle
if errorlevel 1 (
  echo Bundle failed locally — fix errors above before cloud build.
  goto :fail
)

cd /d "%~dp0.."
git diff --quiet mobile/
if errorlevel 1 (
  echo.
  echo WARNING: You have uncommitted changes under mobile/
  echo EAS uploads from GIT — commit and push first, or the cloud build will use old code.
  echo   git add mobile
  echo   git commit -m "mobile update"
  echo   git push
  echo.
  pause
)

cd /d "%~dp0"

echo.
echo Starting EAS cloud build (uses git repo; app path: mobile/)
echo Queue can take 30-45 min on free tier.
echo.
echo Do NOT set EAS_NO_VCS=1 — this repo is a monorepo and EAS needs mobile/ inside the archive.
echo.

call npx.cmd eas build --platform android --profile preview --non-interactive --clear-cache
if errorlevel 1 goto :fail

echo.
echo Download APK from the link above or expo.dev -^> Builds.
pause
exit /b 0

:fail
echo.
echo On expo.dev open the build and check failed phases above "Build complete hook".
pause
exit /b 1
