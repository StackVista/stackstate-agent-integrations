$envName = $args[0]
$pythonVersion = $args[1]
if ($pythonVersion -eq '3') {
  $pythonVersion = '3.13.14'
}

$versionsFile = Join-Path $PSScriptRoot 'python_tool_versions.env'
if (Test-Path $versionsFile) {
  Get-Content $versionsFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.+?)\s*$') {
      Set-Variable -Name $matches[1] -Value $matches[2] -Scope Script
    }
  }
}
if (-not $PIP_VERSION) { $PIP_VERSION = '24.3.1' }
if (-not $SETUPTOOLS_VERSION) { $SETUPTOOLS_VERSION = '75.8.2' }

$envExists = conda env list | Select-String -Pattern "^\s*$([regex]::Escape($envName))\s"
if ($envExists) {
  Write-Output "Virtual Environment '$envName' already exists"
  return
}

conda create -n $envName python python=$pythonVersion -y
conda activate $envName
pip install --user -i https://pypi.python.org/simple "pip==$PIP_VERSION"
pip install --ignore-installed "setuptools==$SETUPTOOLS_VERSION"
