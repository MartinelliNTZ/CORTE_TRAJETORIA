@echo off
title CorteTrajetoria

cd /d "C:\PythonPrograms\CorteTrajetoria"

echo Limpando arquivos __pycache__...
for /d /r %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

echo Removendo arquivos .pyc...
del /s /q "*.pyc" >nul 2>&1

echo Iniciando aplicacao...
python main.py

pause