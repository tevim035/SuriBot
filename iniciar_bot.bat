@echo off
cd /d "%~dp0"
if not exist "venv312\pyvenv.cfg" (
    echo O ambiente ainda nao foi instalado. Rode primeiro o instalar.bat
    pause
    exit /b 1
)

rem O Controle Inteligente de Aplicativos do Windows bloqueia venv312\Scripts\python.exe,
rem entao usamos o Python base da venv (linha "home" do pyvenv.cfg) e o iniciar.py
rem carrega as bibliotecas da venv.
set "PYHOME="
for /f "tokens=1,* delims==" %%a in (venv312\pyvenv.cfg) do (
    if /i "%%a"=="home " set "PYHOME=%%b"
)
set "PYHOME=%PYHOME:~1%"
if not exist "%PYHOME%\python.exe" (
    echo [ERRO] Nao achei o Python em "%PYHOME%". Rode o instalar.bat de novo.
    pause
    exit /b 1
)

rem Abre o Ollama (a IA de conversa) se ele ainda nao estiver aberto.
tasklist /fi "imagename eq ollama app.exe" | find /i "ollama app.exe" >nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
)

echo Ligando o bot... (para desligar, feche esta janela ou aperte Ctrl+C)
echo.
"%PYHOME%\python.exe" iniciar.py
echo.
pause
