$ErrorActionPreference = "Stop"

$py = "C:\Users\doree\AppData\Local\Programs\Python\Python311\python.exe"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $root

Write-Host "Using Python: $py"
& $py -m pip install -r requirements.txt

Write-Host "Starting Streamlit..."
& $py -m streamlit run app.py --server.headless true --server.port 8501
