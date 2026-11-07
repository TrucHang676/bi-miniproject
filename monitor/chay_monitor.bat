@echo off
rem Mo dashboard Theo doi ETL tai http://localhost:8502 (app Tro ly AI dung cong 8501).
rem Can: Postgres dang chay (docker compose up -d), da chay sql\init\06_etl_monitor.sql, da pip install -r monitor\requirements.txt
rem --server.headless true: bo qua cau hoi email cua Streamlit lan dau chay (cau hoi nay chan app cho toi khi bam Enter)
rem   va khong tu mo trinh duyet -> dong "start" ben duoi tu mo http://localhost:8502 sau 5 giay.
cd /d "%~dp0.."
set CO=--server.port 8502 --server.address localhost --server.headless true --browser.gatherUsageStats false --client.toolbarMode minimal
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start "" http://localhost:8502"
where py >nul 2>nul
if errorlevel 1 goto dung_python
py -m streamlit run monitor\app.py %CO%
goto het
:dung_python
python -m streamlit run monitor\app.py %CO%
:het
pause
