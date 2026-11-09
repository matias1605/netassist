param(
    [ValidateSet('Streamlit', 'Web')]
    [string]$Interfaz = 'Streamlit'
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'No se encuentra el entorno .venv del proyecto.'
}

# Estas variables solo afectan a este proceso y a sus procesos hijos.
$env:HF_HOME = Join-Path $PSScriptRoot '.cache/huggingface'
$env:SENTENCE_TRANSFORMERS_HOME = Join-Path $PSScriptRoot '.cache/sentence-transformers'
$env:TORCH_HOME = Join-Path $PSScriptRoot '.cache/torch'
$env:ANONYMIZED_TELEMETRY = 'False'
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'

$puertos = if ($Interfaz -eq 'Streamlit') { @(8501) } else { @(8000, 5500) }
$ocupados = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners().Port
foreach ($puerto in $puertos) {
    if ($puerto -in $ocupados) {
        throw "El puerto $puerto ya esta ocupado. No se ha detenido ni modificado el otro servicio."
    }
}

if ($Interfaz -eq 'Streamlit') {
    & $python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
    exit $LASTEXITCODE
}

# El servidor web se cierra al detener el backend con Ctrl+C.
$frontend = Start-Process -FilePath $python -ArgumentList @('-m', 'http.server', '5500', '--bind', '127.0.0.1', '--directory', 'frontend') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
try {
    Write-Host 'NetAssist web: http://localhost:5500'
    & $python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} finally {
    if (-not $frontend.HasExited) {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $frontend.Id /T /F | Out-Null
    }
}
