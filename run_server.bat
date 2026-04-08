@echo off
TITLE FastAPI Server 

if not exist .venv (
    echo [ERROR] No se encontro la carpeta .venv. 
    echo Creando entorno virtual...
    python -m venv .venv
    echo Instalando dependencias...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    echo Activando entorno virtual...
    call .venv\Scripts\activate.bat
)

echo Lanzando FastAPI en http://192.168.1.67:8000
echo Presiona Ctrl+C para detener el servidor.
uvicorn app.server:app --reload --host 127.0.0.1 --port 8000


pause