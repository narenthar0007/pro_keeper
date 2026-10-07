@echo off
cd /d "%~dp0"
echo Log in to Expo (https://expo.dev) for EAS cloud builds.
if not exist "node_modules\" call npm.cmd install
call npm.cmd run eas:login
pause
