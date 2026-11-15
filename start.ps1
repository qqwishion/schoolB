$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:DEBUG = 'True'
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& ./.venv/Scripts/python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& ./.venv/Scripts/python.exe manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo content creation failed' }
& ./.venv/Scripts/python.exe manage.py create_demo_users
if ($LASTEXITCODE -ne 0) { throw 'Demo accounts creation failed' }
& ./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
