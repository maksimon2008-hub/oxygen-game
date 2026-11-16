@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
title OXYGEN WEB - Pygbag
py -3.12 -m pip show pygbag >nul 2>&1
if errorlevel 1 (
  echo [УСТАНОВКА] Устанавливаю Pygbag...
  py -3.12 -m pip install --upgrade pygbag
  if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить Pygbag. Проверь интернет.
    pause
    exit /b 1
  )
)
echo [OXYGEN WEB] Подготовка браузерной сборки и локального сервера...
py -3.12 -m pygbag oxygen_web
if errorlevel 1 (
  echo.
  echo [ОШИБКА] Pygbag завершился с ошибкой.
  pause
)
