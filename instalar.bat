@echo off
cd /d "%~dp0"
echo ==========================================
echo  Instalando o ambiente do bot (Python 3.12)
echo ==========================================
echo.

set "PY="
call :achar_python

if not defined PY (
    echo Python 3.12 nao encontrado. Instalando pelo winget...
    echo.
    winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
    call :achar_python
)

if not defined PY (
    echo.
    echo [ERRO] Nao consegui instalar ou encontrar o Python 3.12.
    echo Instale manualmente pelo site python.org/downloads ^(versao 3.12^)
    echo marcando "Add python.exe to PATH", e rode este arquivo de novo.
    pause
    exit /b 1
)

echo Usando: %PY%
echo.

if not exist "venv312\Scripts\python.exe" (
    echo Criando o ambiente virtual venv312...
    "%PY%" -m venv venv312
)

echo.
echo Instalando as bibliotecas (pode demorar varios minutos)...
echo.
venv312\Scripts\python.exe -m pip install --upgrade pip
venv312\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] A instalacao das bibliotecas falhou. Copie as mensagens acima e mande para o Claude.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Tudo pronto! Para ligar o bot, de dois
echo  cliques em iniciar_bot.bat
echo ==========================================
pause
exit /b 0

:achar_python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & exit /b 0
if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe" & exit /b 0
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
exit /b 0
