@echo off
Running WebGIS in local.
cd /d "%~dp0docs"
echo ============================================================
echo  Indonesia Flood Risk EWS - local
echo  open in browser: http://127.0.0.1:5500

echo ============================================================
start "" http://127.0.0.1:5500
python -m http.server 5500
