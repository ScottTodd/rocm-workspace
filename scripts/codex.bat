@echo off
REM Launch Codex from the ROCm meta-workspace.
REM
REM Codex commands should invoke task-specific tool environments explicitly.
REM For example, TheRock build_tools tests should use:
REM   ..\TheRock\.venv\Scripts\python.exe -m pytest

setlocal

set SCRIPT_DIR=%~dp0
set WORKSPACE_DIR=%SCRIPT_DIR%..

REM Change to workspace directory and launch Codex
cd /d "%WORKSPACE_DIR%"

REM Sandbox and writable root defaults are project-local in .codex/config.toml
REM so CLI, app, and resumed sessions use the same checked-in policy.
if not exist "D:\scratch\codex" mkdir "D:\scratch\codex"

codex %*
