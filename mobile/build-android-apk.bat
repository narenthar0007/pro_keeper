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

echo Checking JavaScript bundle (same step EAS runs)...
call npm.cmd run verify:bundle
if errorlevel 1 (
  echo Bundle failed locally — fix errors above before cloud build.
  goto :fail
)

echo.
echo Uploading THIS folder to EAS (EAS_NO_VCS=1), not only last git commit.
echo Queue can take 30-45 min on free tier; build ~10-20 min after that.
echo.

set EAS_NO_VCS=1
call npx.cmd eas build --platform android --profile preview --non-interactive --clear-cache
if errorlevel 1 goto :fail

echo.
echo Download APK from the link above or expo.dev -^> Builds.
pause
exit /b 0

:fail
echo.
echo If cloud build failed, open the build on expo.dev and expand
echo "Bundle JavaScript" or "Run gradlew" for the real error.
pause
exit /b 1
