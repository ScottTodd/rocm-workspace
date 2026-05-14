@echo off
REM Launch Codex with the workspace Python venv activated.
REM
REM Setup (one-time):
REM   cd D:\projects\rocm-workspace
REM   py -V:3.12 -m venv 3.12.venv
REM   .\3.12.venv\Scripts\activate.bat
REM   pip install -r ..\TheRock\requirements.txt
REM
REM This ensures tools like pytest are available when Codex runs commands.

setlocal

set SCRIPT_DIR=%~dp0
set WORKSPACE_DIR=%SCRIPT_DIR%..

REM Activate the workspace venv
call "%WORKSPACE_DIR%\3.12.venv\Scripts\activate.bat"

REM Change to workspace directory and launch Codex
cd /d "%WORKSPACE_DIR%"

REM Allow Codex to work in the common sibling repositories from this
REM meta-workspace. Missing directories are skipped so the launcher still works
REM on machines with a partial checkout.
set CODEX_ADD_DIRS=
if exist "%WORKSPACE_DIR%\..\TheRock" set CODEX_ADD_DIRS=%CODEX_ADD_DIRS% --add-dir "%WORKSPACE_DIR%\..\TheRock"
if exist "%WORKSPACE_DIR%\..\rockrel" set CODEX_ADD_DIRS=%CODEX_ADD_DIRS% --add-dir "%WORKSPACE_DIR%\..\rockrel"

codex --sandbox workspace-write %CODEX_ADD_DIRS% %*
