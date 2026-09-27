@echo off
setlocal
cd /d "%~dp0"
title Service App - iniciando

echo Comprobando Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop no esta corriendo. Intentando abrirlo...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else (
        echo No se encontro Docker Desktop. Abrilo a mano y volve a ejecutar este archivo.
        pause
        exit /b 1
    )
    echo Esperando a que Docker este listo, puede tardar un par de minutos...
    powershell -NoProfile -Command "$t=0; while ($t -lt 240) { docker info *> $null; if ($LASTEXITCODE -eq 0) { exit 0 }; Start-Sleep 3; $t+=3 }; exit 1"
    if errorlevel 1 (
        echo Docker no termino de iniciar. Volve a ejecutar este archivo en un momento.
        pause
        exit /b 1
    )
)

echo Iniciando la aplicacion...
docker compose up -d --build
if errorlevel 1 (
    echo Hubo un error al iniciar. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo Esperando a que la aplicacion responda...
powershell -NoProfile -Command "$t=0; while ($t -lt 120) { try { if ((Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep 2; $t+=2 }; exit 1"
if errorlevel 1 (
    echo La aplicacion no respondio a tiempo. Para ver que paso: docker compose logs app
    pause
    exit /b 1
)

start "" http://127.0.0.1:5000
echo Listo: la aplicacion se abrio en tu navegador.
ping -n 4 127.0.0.1 >nul
