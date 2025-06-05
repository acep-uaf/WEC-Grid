function Write-Color {
    param (
        [string]$Message,
        [string]$Color = "White"
    )
    $Host.UI.RawUI.ForegroundColor = $Color
    Write-Output $Message
    $Host.UI.RawUI.ForegroundColor = "White"
}

# --- Global Variables ---
$Global:DefaultPssePath = "C:\Program Files\PTI\PSSE35\35.3"
$Global:DefaultMatlabPath = "C:\Program Files\MATLAB\R2021b"

# Prompt for Conda environment name
$Global:CondaEnvName = Read-Host "Enter the name for the Conda environment (default: WecGridEnv)"
if (-not $Global:CondaEnvName) {
    $Global:CondaEnvName = "WecGridEnv"  # Use default if no input is provided
}

# YML file for environment creation
$Global:CondaEnvFile = "wec_grid_env.yml"
Write-Color "Using Conda environment: $Global:CondaEnvName" "Cyan"

# --- Helper Functions ---

function Verify-Command {
    param (
        [string]$CommandName,
        [string]$ErrorMessage
    )
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        Write-Color $ErrorMessage "Red"
        exit 1
    }
}

function Check-CondaEnvironmentExists {
    param (
        [string]$envName
    )
    $condaEnvs = conda env list | ForEach-Object { $_.Trim() } | Where-Object { -not ($_ -match "^#") }
    if ($condaEnvs -contains $envName) {
        Write-Color "Conda environment '$envName' already exists." "Yellow"
        return $false
    } else {
        Write-Color "Conda environment '$envName' does not exist." "Cyan"
        return $true
    }
}

# --- Step 1: Check and Create Conda Environment ---
function Setup-CondaEnvironment {
    Write-Color "Step 1: Setting up Conda environment from YML..." "Cyan"
    Verify-Command "conda" "'conda' is NOT installed or not found in PATH. Please install Miniconda or Anaconda."

    if (-not (Test-Path $Global:CondaEnvFile)) {
        Write-Color "YAML file '$Global:CondaEnvFile' not found. Cannot create Conda environment." "Red"
        exit 1
    }

    if ((Check-CondaEnvironmentExists -envName $Global:CondaEnvName)) {
        conda env create -n $Global:CondaEnvName -f $Global:CondaEnvFile
        if (-not $?) {
            Write-Color "Failed to create Conda environment '$Global:CondaEnvName'." "Red"
            exit 1
        }
    } else {
        Write-Color "Skipping environment creation since it already exists." "Yellow"
    }

    conda activate $Global:CondaEnvName
    $activeEnv = conda info --json | ConvertFrom-Json | Select-Object -ExpandProperty active_prefix
    if (-not ($activeEnv -match $Global:CondaEnvName)) {
        Write-Color "Failed to activate the Conda environment '$Global:CondaEnvName'." "Red"
        exit 1
    }

    Write-Color "Conda environment '$Global:CondaEnvName' is ready and activated." "Green"

    # Verify installed packages
    Write-Color "`n Verifying installed packages from $Global:CondaEnvFile..." "Cyan"
    $ymlContent = Get-Content $Global:CondaEnvFile -Raw
    $dependencies = ($ymlContent -split "`n") | Where-Object { $_ -match "^- " } | ForEach-Object { ($_ -replace "^- ", "").Trim() }

    $missingPackages = @()
    foreach ($pkg in $dependencies) {
        $pkgName = if ($pkg -match "=") { $pkg.Split("=")[0] } else { $pkg }
        if (-not (conda list | Select-String -Quiet $pkgName)) {
            $missingPackages += $pkgName
        }
    }

    if ($missingPackages.Count -eq 0) {
        Write-Color "All packages specified in $Global:CondaEnvFile are installed." "Green"
    } else {
        Write-Color "`nThe following packages are NOT installed:" "Red"
        $missingPackages | ForEach-Object { Write-Color "- $_" "Yellow" }
        exit 1
    }
}

# --- Step 2: Install WecGrid ---
function Install-WecGrid {
    Write-Color "`nStep 2: Installing WecGrid package..." "Cyan"

    if (-not (Test-Path "./setup.py")) {
        Write-Color "The 'setup.py' file for WecGrid is not found in the current directory." "Red"
        exit 1
    }

    pip install -e .
    if (-not $?) {
        Write-Color "Failed to install WecGrid package." "Red"
        exit 1
    }

    Write-Color "`n Verifying WecGrid is configured and accessible..." "Cyan"
    try {
        python -c "import WecGrid" 2>&1 | Out-Null
        Write-Color "WecGrid is configured and accessible." "Green"
    } catch {
        Write-Color "WecGrid is NOT configured or accessible." "Red"
        exit 1
    }

    python -m ipykernel install --user --name=$Global:CondaEnvName --display-name "Python ($Global:CondaEnvName)"
    Write-Color "WecGrid installed successfully!" "Green"
}

# --- Step 3: Configure PSSE ---
function Configure-PSSE-Persistent {
    param (
        [string]$PsseBasePath = "C:\Program Files\PTI\PSSE35\35.3"
    )

    # Validate Conda environment name
    if (-not $Global:CondaEnvName) {
        Write-Output "Error: Conda environment name is not defined."
        return
    }

    Write-Output "Configuring PSSE environment variables for Conda environment '$Global:CondaEnvName'..."

    # Define the paths
    $pssePaths = @(
        "$PsseBasePath\PSSPY37",
        "$PsseBasePath\PSSBIN",
        "$PsseBasePath\PSSLIB",
        "$PsseBasePath\EXAMPLE"
    )

    # Directory for activate.d
    $activateDir = "$env:CONDA_PREFIX\etc\conda\activate.d"

    # Ensure directory exists
    if (-not (Test-Path $activateDir)) { New-Item -ItemType Directory -Path $activateDir -Force }

    # Write activate.ps1
    $activatePs1 = @"
# Add PSSE paths only if not already set
if (-not `$Env:PSSE_PATHS_SET) {
    `$Env:PATH += ";$($pssePaths -join ";")"
    `$Env:PYTHONPATH = "$PsseBasePath\PSSPY37"
    `$Env:PSSE_PATHS_SET = "1"
}
"@
    $activateFile = "$activateDir\set_psse_paths.ps1"
    Set-Content -Path $activateFile -Value $activatePs1
    Write-Output "Created: $activateFile"

    Write-Output "PSSE environment configuration is complete for Conda environment '$Global:CondaEnvName'."
    Write-Output "Activate the environment to apply the changes."
    #TODO: need to add verify code
    # deactivate 
    # activate $Global:CondaEnvName
    # test - python -c "import psse35; import pssepy" 2>&1 | Out-Null
}



# --- Step 4: Configure MATLAB ---
function Configure-MATLAB {
    Write-Color "`nStep 4: Configuring MATLAB Engine API..." "Cyan"

    if (-not $env:MATLAB_PATH) {
        $env:MATLAB_PATH = $Global:DefaultMatlabPath
    }

    while (-not (Test-Path -Path $env:MATLAB_PATH)) {
        Write-Color "Invalid MATLAB path: '$env:MATLAB_PATH'. Please enter a valid path." "Red"
        $env:MATLAB_PATH = Read-Host "Enter the correct MATLAB installation path"
    }

    $matlabEnginePath = "$env:MATLAB_PATH\extern\engines\python"
    if (-not (Test-Path -Path $matlabEnginePath)) {
        Write-Color "Invalid MATLAB Engine path: '$matlabEnginePath'. Please check and try again." "Red"
        exit 1
    }

    Write-Color "Installing MATLAB Engine API..." "Yellow"
    Push-Location $matlabEnginePath
    python -m pip install . --force-reinstall
    python -m pip install matlabengine
    Pop-Location

    #TODO: need to fix this verify code
    # [System.Environment]::SetEnvironmentVariable("MATLAB_PATH", $env:MATLAB_PATH, [System.EnvironmentVariableTarget]::User)
    # Write-Color "MATLAB paths configured successfully!" "Green"

    # Write-Color "`n Verifying MATLAB Engine API is installed..." "Cyan"
    # try {
    #     python -c "import matlab.engine" 2>&1 | Out-Null
    #     Write-Color "'matlab.engine' is installed and accessible." "Green"
    # } catch {
    #     Write-Color "'matlab.engine' is NOT installed or accessible." "Red"
    #     exit 1
    # }
}

# --- Main Script Execution ---
Setup-CondaEnvironment
Install-WecGrid
Configure-PSSE-Persistent
Configure-MATLAB
conda deactivate
conda activate $Global:CondaEnvName
Write-Color "`nSetup complete! Your environment is ready." "Yellow"