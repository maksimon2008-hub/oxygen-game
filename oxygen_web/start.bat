@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OXYGEN - Python Platformer

echo ========================================
echo               OXYGEN v2.1
echo ========================================
echo.

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python 3.12 x64 не найден.
    echo Установи Python 3.12: https://www.python.org/downloads/release/python-31210/
    echo Во время установки оставь включённым Python Launcher (py).
    pause
    exit /b 1
)

py -3.12 -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo [УСТАНОВКА] Устанавливаю pygame-ce для Python 3.12...
    py -3.12 -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось обновить pip.
        pause
        exit /b 1
    )
    py -3.12 -m pip install --only-binary=:all: -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить pygame-ce. Проверь интернет-соединение.
        pause
        exit /b 1
    )
)

echo.
echo [OXYGEN] Запуск игры...
py -3.12 main.py
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Игра завершилась с ошибкой. Скопируй сообщение выше.
    pause
)
