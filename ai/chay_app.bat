@echo off
rem Mo app Tro ly AI tai http://localhost:8501 (nut robot trong Power BI tro toi dia chi nay).
rem Can: Postgres dang chay (docker compose up -d), .env co GEMINI_API_KEY, da pip install -r ai\requirements.txt
cd /d "%~dp0.."
python -m streamlit run ai\app.py --server.port 8501
pause
