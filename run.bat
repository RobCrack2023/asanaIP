@echo off
title AsanaIP - Servidor Local
color 0A

echo ========================================
echo        AsanaIP - Iniciando...
echo ========================================
echo.

:: Copiar .env si no existe
if not exist ".env" (
    echo [!] No se encontro .env. Creando desde .env.example...
    copy .env.example .env >nul
    echo      Archivo .env creado. Editalo antes de usar en produccion.
    echo.
)

:: Verificar que existe el entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [!] No se encontro el entorno virtual. Creandolo...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install django djangorestframework django-cors-headers pillow python-dotenv
    echo.
) else (
    call venv\Scripts\activate.bat
    pip install python-dotenv -q
)

:: Verificar que existen las dependencias del frontend
if not exist "frontend\node_modules" (
    echo [!] Instalando dependencias del frontend...
    cd frontend
    npm install
    cd ..
    echo.
)

:: Aplicar migraciones pendientes
echo [1/4] Aplicando migraciones de base de datos...
python manage.py migrate --run-syncdb 2>nul
echo      Listo.
echo.

:: Verificar si hay datos de prueba
python -c "import os,django;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();from core.models import User;exit(0 if User.objects.exists() else 1)" 2>nul
if %errorlevel% neq 0 (
    echo [2/4] Cargando datos de prueba...
    python seed_data.py
    echo.
) else (
    echo [2/4] Base de datos ya tiene datos.
    echo.
)

:: Iniciar Django en segundo plano
echo [3/4] Iniciando servidor Django en puerto 8000...
start /B "Django" python manage.py runserver 0.0.0.0:8000 >nul 2>&1
timeout /t 2 /nobreak >nul
echo      Django corriendo en http://127.0.0.1:8000
echo.

:: Iniciar frontend
echo [4/4] Iniciando frontend React en puerto 5173...
echo.
echo ========================================
echo   App lista en: http://localhost:5173
echo.
echo   Credenciales:
echo     Admin:    admin / admin123
echo     Usuarios: carlos, maria, pedro,
echo               ana, luis / pass123
echo.
echo   Presiona Ctrl+C para detener todo.
echo ========================================
echo.

cd frontend
npm run dev
