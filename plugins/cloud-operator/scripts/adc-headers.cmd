@echo off
rem Copyright 2026 Google LLC
rem
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.
rem You may obtain a copy of the License at
rem
rem     http://www.apache.org/licenses/LICENSE-2.0
rem
rem Unless required by applicable law or agreed to in writing, software
rem distributed under the License is distributed on an "AS IS" BASIS,
rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
rem See the License for the specific language governing permissions and
rem limitations under the License.
rem
rem Windows version of scripts/adc-headers, the Claude Code headersHelper for
rem the plugin's MCP servers. .mcp.json names the helper without an extension,
rem so CMD runs this file. Prints the HTTP headers for one connection as a JSON
rem object: a fresh Application Default Credentials access token and the quota
rem project (x-goog-user-project): the ADC file's quota_project_id, else
rem gcloud's billing/quota_project, else the gcloud project. Never prints
rem anything but the headers; errors go to stderr.

setlocal

where gcloud >nul 2>nul
if errorlevel 1 (
  >&2 echo gcloud isn't installed or isn't on PATH: install the Google Cloud CLI, then run: gcloud auth application-default login
  exit /b 1
)

set "TOKEN="
for /f "usebackq delims=" %%T in (`gcloud auth application-default print-access-token 2^>nul`) do set "TOKEN=%%T"
if not defined TOKEN (
  >&2 echo Couldn't get a token from "gcloud auth application-default print-access-token". If you haven't signed in, run: gcloud auth application-default login. Otherwise, run that command yourself to see the error.
  exit /b 1
)

set "CONFIG=%CLOUDSDK_CONFIG%"
if not defined CONFIG set "CONFIG=%APPDATA%\gcloud"
set "ADC=%CONFIG%\application_default_credentials.json"
set "QUOTA="
if exist "%ADC%" for /f "usebackq tokens=2 delims=:, " %%Q in (`findstr /c:quota_project_id "%ADC%"`) do set "QUOTA=%%~Q"
set "BQ="
if not defined QUOTA for /f "usebackq delims=" %%Q in (`gcloud config get-value billing/quota_project 2^>nul`) do set "BQ=%%Q"
rem Values gcloud accepts for billing/quota_project that aren't project IDs.
if /i "%BQ%"=="CURRENT_PROJECT" set "BQ="
if /i "%BQ%"=="CURRENT_PROJECT_WITH_FALLBACK" set "BQ="
if /i "%BQ%"=="LEGACY" set "BQ="
if not defined QUOTA set "QUOTA=%BQ%"
if not defined QUOTA for /f "usebackq delims=" %%Q in (`gcloud config get-value project 2^>nul`) do set "QUOTA=%%Q"

if defined QUOTA (
  echo {"Authorization":"Bearer %TOKEN%","x-goog-user-project":"%QUOTA%"}
) else (
  echo {"Authorization":"Bearer %TOKEN%"}
)
