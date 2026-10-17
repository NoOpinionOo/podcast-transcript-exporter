param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $project "dist"
$work = Join-Path $project "build"

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $dist `
    --workpath $work `
    (Join-Path $project "Podcast-Transkript-Exporter.spec")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller-Build fehlgeschlagen (Exitcode $LASTEXITCODE)."
}

Write-Host "Fertig: $dist\Podcast-Transkript-Exporter.exe"

