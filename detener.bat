@echo off
cd /d "%~dp0"
title Service App - deteniendo

echo Deteniendo la aplicacion. Antes de cerrar se guarda un backup en la carpeta backups...
docker compose stop
echo Listo. Ya podes cerrar Docker Desktop si queres.
ping -n 4 127.0.0.1 >nul
