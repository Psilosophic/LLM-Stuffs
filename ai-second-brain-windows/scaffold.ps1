<#
.SYNOPSIS
  Scaffold the Brain vault for the AI Second Brain (Windows) skill.
.DESCRIPTION
  Creates <Desktop>\Brain with raw\, wiki\, a seeded wiki\index.md, log.md and
  the Karpathy CLAUDE.md. Resolves the REAL Desktop via the shell folder API so
  OneDrive redirection doesn't silently break the path. Optionally installs the
  /today /ideas /create slash commands into %USERPROFILE%\.claude\commands.
.NOTES
  Run from this folder:  powershell -ExecutionPolicy Bypass -File .\scaffold.ps1
#>

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Resolve the real Desktop (works whether or not it's redirected into OneDrive).
$desktop = [Environment]::GetFolderPath('Desktop')
$brain   = Join-Path $desktop 'Brain'

Write-Host "Scaffolding Brain at: $brain"

# Folders
New-Item -ItemType Directory -Force -Path (Join-Path $brain 'raw')  | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $brain 'wiki') | Out-Null

# Seed files from the template, but never clobber an existing vault.
$template = Join-Path $here 'brain-template'
$copies = @(
  @{ src = 'CLAUDE.md';      dst = 'CLAUDE.md' }
  @{ src = 'log.md';         dst = 'log.md' }
  @{ src = 'wiki\index.md';  dst = 'wiki\index.md' }
)
foreach ($c in $copies) {
  $dstPath = Join-Path $brain $c.dst
  if (Test-Path $dstPath) {
    Write-Host "  skip (exists): $($c.dst)"
  } else {
    Copy-Item (Join-Path $template $c.src) $dstPath
    Write-Host "  created: $($c.dst)"
  }
}

# Slash commands
$answer = Read-Host "Install /today /ideas /create into your Claude Code commands? (y/N)"
if ($answer -match '^(y|yes)$') {
  $cmdDir = Join-Path $env:USERPROFILE '.claude\commands'
  New-Item -ItemType Directory -Force -Path $cmdDir | Out-Null
  Get-ChildItem (Join-Path $here 'commands') -Filter *.md | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $cmdDir $_.Name) -Force
    Write-Host "  installed command: $($_.Name)"
  }
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. Open '$brain' in Obsidian (Open folder as vault)."
Write-Host "  2. Drop sources into '$([IO.Path]::Combine($brain,'raw'))'."
Write-Host "  3. cd `"$brain`"; claude   then: 'Compile the sources in raw\ per CLAUDE.md.'"
Write-Host "  4. Phone access: see telegram\README.md"
