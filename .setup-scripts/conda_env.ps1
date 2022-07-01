$envName = $args[0]
$pythonVersion = $args[1]
if ($pythonVersion -eq '3') {
  $pythonVersion = '3.8'
}
$env_name = conda env list | grep $envName | awk '{print $1}'
if (($env_name -ne $null) -and ($env_name -eq  $envName)) {
  Write-Output "Virtual Environment '$envName' already exists, removing it for now. Revert later"
  conda env remove -n $envName
}
$DD_PIP_VERSION = '21.3.1'
$DD_SETUPTOOLS_VERSION = '44.1.1'
conda create -n $envName python python=$pythonVersion -y
conda activate $envName
pip install -i https://pypi.python.org/simple pip==$DD_PIP_VERSION
pip install --ignore-installed setuptools==$DD_SETUPTOOLS_VERSION
