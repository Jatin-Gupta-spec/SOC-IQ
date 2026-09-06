#Requires -Version 5.1
<#
.SYNOPSIS
    SOC-IQ Part 3A-2B Windows release build.

.DESCRIPTION
    Orchestrates, on an actual Windows release machine, the two build steps that
    packaging/README.md (Part 3A-2A) already documents as separate manual commands:

      1. Freeze the Python backend into src-tauri/binaries/socq-backend-<target-triple>.exe
         via packaging/scripts/build_backend.py (PyInstaller).
      2. Build the Tauri application (frontend + Rust shell + MSI/NSIS installers) via
         `cargo tauri build`, now that tauri.conf.json's bundle.targets is explicitly
         ["msi", "nsis"] (Part 3A-2B).

    This script does not invent a new build system -- it is a thin sequencer over the
    exact same commands packaging/README.md already describes, so there is exactly one
    documented production build path, run manually or via this script.

    This script only VALIDATES on Windows. It has not been executed here: this Part
    3A-2B checkpoint was produced in a Linux sandbox with no Rust toolchain and no
    Windows host, so running this script is Windows-environment-blocked in that sandbox
    (see the Part 3A-2B final report, "Environment-Blocked"). Static review only.

.NOTES
    Must be run from the project root, or pass -ProjectRoot explicitly.
#>

param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$TargetTriple = "",
    [switch]$SkipBackend
)

$ErrorActionPreference = "Stop"

Write-Host "SOC-IQ Windows release build (Part 3A-2B)" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# --- Step 1: freeze the Python backend sidecar -----------------------------
if (-not $SkipBackend) {
    Write-Host "`n[1/2] Building Python backend sidecar (PyInstaller)..." -ForegroundColor Cyan
    Push-Location $ProjectRoot
    try {
        $backendArgs = @("packaging/scripts/build_backend.py")
        if ($TargetTriple -ne "") {
            $backendArgs += @("--target-triple", $TargetTriple)
        }
        python @backendArgs
        if ($LASTEXITCODE -ne 0) {
            throw "build_backend.py failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "`n[1/2] Skipping backend build (-SkipBackend); assuming " `
        "src-tauri/binaries/socq-backend-<target-triple>.exe already exists." -ForegroundColor Yellow
}

# --- Step 2: build the Tauri application (frontend + Rust + installers) ---
Write-Host "`n[2/2] Building Tauri application (frontend, Rust shell, MSI/NSIS)..." -ForegroundColor Cyan
Push-Location (Join-Path $ProjectRoot "src-tauri")
try {
    cargo tauri build
    if ($LASTEXITCODE -ne 0) {
        throw "cargo tauri build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host "`nDone. Installers are under src-tauri/target/release/bundle/{msi,nsis}/." -ForegroundColor Green
