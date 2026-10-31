@echo off
setlocal
set "KEY=%USERPROFILE%\.ssh\liam1_windows_transport_ed25519"
if exist "%KEY%" goto :show
if not exist "%USERPROFILE%\.ssh" mkdir "%USERPROFILE%\.ssh"
(echo. & echo.) | "%WINDIR%\System32\OpenSSH\ssh-keygen.exe" -q -t ed25519 -C "fleet-liam1-windows-transport" -f "%KEY%"
if errorlevel 1 exit /b 1
:show
type "%KEY%.pub"
