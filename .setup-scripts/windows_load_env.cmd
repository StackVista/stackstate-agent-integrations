call python -m pip install .\stackstate_checks_dev[cli]
IF %ERRORLEVEL% NEQ 0 (
  call python -m pip install .\stackstate_checks_dev[cli]
)
IF %ERRORLEVEL% NEQ 0 (
  call python -m pip install .\stackstate_checks_dev[cli]
)
