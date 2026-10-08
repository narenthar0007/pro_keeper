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
  echo Bundle failed locally. Fix errors above before cloud build.
  goto :fail
)

cd /d "%~dp0.."
git diff --quiet mobile/
if errorlevel 1 (
  echo.
  echo WARNING: Uncommitted changes under mobile/
  echo EAS uses git. Commit and push first:
  echo   git add mobile .easignore
  echo   git commit -m "mobile update"
  echo   git push
  echo.
  pause
)
cd /d "%~dp0"

echo.
echo Starting EAS cloud build (git upload: mobile/ only via .easignore)
echo Queue can take 30-45 min on free tier; build ~15-25 min after that.
echo.

call npx.cmd eas build --platform android --profile preview --non-interactive --clear-cache
if errorlevel 1 goto :fail

echo.
echo Download APK from the link above or expo.dev Builds.
pause
exit /b 0

:fail
echo.
echo If it failed in under 1 minute, check expo.dev build log for "tar:" or "package.json".
pause
exit /b 1
