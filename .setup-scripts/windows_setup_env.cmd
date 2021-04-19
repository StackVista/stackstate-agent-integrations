set WIN_CI_PROJECT_DIR=%CD%
set WORKON_HOME=%WIN_CI_PROJECT_DIR%

set

dir

rmdir /q /s %WORKON_HOME%\venv
call mkvirtualenv venv

echo call %WORKON_HOME%\venv\Scripts\activate.bat
call %WORKON_HOME%\venv\Scripts\activate.bat
