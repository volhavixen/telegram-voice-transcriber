$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
    $PythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
    $PythonArgs = @()
} else {
    Write-Error "Python 3 не найден. Установите Python 3.10–3.14 с https://www.python.org/downloads/"
}

& $PythonExe @PythonArgs -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 'Нужен Python 3.10–3.14')"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $PythonExe @PythonArgs -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Создан файл .env — впишите в него BOT_TOKEN и ALLOWED_USER_IDS."
} else {
    Write-Host "Файл .env уже существует и сохранён без изменений."
}

Write-Host "Установка завершена. После настройки .env запустите start.bat."
Read-Host "Нажмите Enter для выхода"
