set WIN_CI_PROJECT_DIR=%CD%
set WORKON_HOME=%WIN_CI_PROJECT_DIR%

set

dir

IF EXIST %WORKON_HOME%\venv GOTO VENV_EXIST
call mkvirtualenv venv
:VENV_EXIST

echo call %WORKON_HOME%\venv\Scripts\activate.bat
call %WORKON_HOME%\venv\Scripts\activate.bat

echo call %WORKON_HOME%\.setup-scripts\windows_load_env.cmd
call %WORKON_HOME%\.setup-scripts\windows_load_env.cmd
