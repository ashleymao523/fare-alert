# v0.51: one-shot deploy refresh - worker first (new fetch code),
# then webui (new API/UI). Run this after every code update so the
# running processes can never lag the deployed files again.
param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
& (Join-Path $PSScriptRoot "restart_worker.ps1") -RepoDir $RepoDir
& (Join-Path $PSScriptRoot "restart_webui.ps1") -RepoDir $RepoDir
