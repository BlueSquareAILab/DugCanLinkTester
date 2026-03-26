param(
    [ValidateSet("All", "MonitorOnly", "MonitorHID")]
    [string]$Target = "All"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot "dist"
$releaseRoot = Join-Path $repoRoot "release"

function Assert-PyInstaller {
    uv run pyinstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not available. Run: uv sync --group build"
    }
}

function Assert-HidDependency {
    @'
import importlib.util
import sys

if importlib.util.find_spec("vgamepad") is None:
    print("vgamepad is not installed. Run: uv sync --group build --extra hid")
    sys.exit(1)
'@ | uv run python - | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "vgamepad is not installed. Run: uv sync --group build --extra hid"
    }
}

function Remove-IfExists([string]$PathValue) {
    if (Test-Path -LiteralPath $PathValue) {
        Remove-Item -LiteralPath $PathValue -Recurse -Force
    }
}

function Compress-WithRetry(
    [string]$SourcePath,
    [string]$DestinationPath
) {
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Compress-Archive -LiteralPath $SourcePath -DestinationPath $DestinationPath
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw
            }
            Start-Sleep -Seconds 2
        }
    }
}

function Build-ZipFromSpec(
    [string]$SpecPath,
    [string]$DistFolderName,
    [string]$ZipFileName,
    [switch]$RequiresHid
) {
    if ($RequiresHid) {
        Assert-HidDependency
    }

    Remove-IfExists (Join-Path $distRoot $DistFolderName)
    Remove-IfExists (Join-Path $releaseRoot $ZipFileName)

    uv run pyinstaller --clean --noconfirm $SpecPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed: $SpecPath"
    }

    $builtFolder = Join-Path $distRoot $DistFolderName
    if (-not (Test-Path -LiteralPath $builtFolder)) {
        throw "Expected build output not found: $builtFolder"
    }

    if (-not (Test-Path -LiteralPath $releaseRoot)) {
        New-Item -ItemType Directory -Path $releaseRoot | Out-Null
    }

    Compress-WithRetry `
        -SourcePath $builtFolder `
        -DestinationPath (Join-Path $releaseRoot $ZipFileName)
}

Push-Location $repoRoot
try {
    Assert-PyInstaller

    switch ($Target) {
        "All" {
            Build-ZipFromSpec `
                -SpecPath "packaging\monitor_only.spec" `
                -DistFolderName "DugCanLinkTester-MonitorOnly-win64" `
                -ZipFileName "DugCanLinkTester-MonitorOnly-win64.zip"

            Build-ZipFromSpec `
                -SpecPath "packaging\monitor_hid.spec" `
                -DistFolderName "DugCanLinkTester-MonitorHID-win64" `
                -ZipFileName "DugCanLinkTester-MonitorHID-win64.zip" `
                -RequiresHid
        }
        "MonitorOnly" {
            Build-ZipFromSpec `
                -SpecPath "packaging\monitor_only.spec" `
                -DistFolderName "DugCanLinkTester-MonitorOnly-win64" `
                -ZipFileName "DugCanLinkTester-MonitorOnly-win64.zip"
        }
        "MonitorHID" {
            Build-ZipFromSpec `
                -SpecPath "packaging\monitor_hid.spec" `
                -DistFolderName "DugCanLinkTester-MonitorHID-win64" `
                -ZipFileName "DugCanLinkTester-MonitorHID-win64.zip" `
                -RequiresHid
        }
    }
}
finally {
    Pop-Location
}
