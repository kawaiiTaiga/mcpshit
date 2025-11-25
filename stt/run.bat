@echo off

REM --- Conda base 환경 활성화 ---
call "C:\Users\gaterbelt\anaconda3\Scripts\activate.bat" base

REM --- GUI 실행 (콘솔 없는 파이썬) ---
"C:\Users\gaterbelt\anaconda3\pythonw.exe" "C:\Users\gaterbelt\Downloads\stt\gui.py"
