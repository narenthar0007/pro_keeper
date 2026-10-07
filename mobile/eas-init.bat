@echo off
cd /d "%~dp0"
if not exist "node_modules\" call npm.cmd install
echo Links this app to your Expo account (creates project on expo.dev).
call npm.cmd run eas:init
pause
