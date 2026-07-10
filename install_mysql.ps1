$ErrorActionPreference = "Stop"

$MySQLVersion = "8.0.29"
$InstallDir = "C:\mysql"
$DataDir = "$InstallDir\data"
$RootPassword = ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MySQL $MySQLVersion one-click install" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$DownloadsDir = "$env:USERPROFILE\Downloads"
$DesktopDir = "$env:USERPROFILE\Desktop"
$CurrentDir = Get-Location

$ZipPaths = @(
    "D:\mysql-8.0.29-winx64.zip",
    "$DownloadsDir\mysql-$MySQLVersion-winx64.zip",
    "$DesktopDir\mysql-$MySQLVersion-winx64.zip",
    "$CurrentDir\mysql-$MySQLVersion-winx64.zip"
)

$zipFile = $null
foreach ($path in $ZipPaths) {
    $found = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $zipFile = $found.FullName
        break
    }
}

if (-not $zipFile) {
    Write-Host "ERROR: MySQL zip not found!" -ForegroundColor Red
    Write-Host "Download: https://mirrors.huaweicloud.com/mysql/Downloads/MySQL-8.0/mysql-8.0.29-winx64.zip" -ForegroundColor Blue
    pause
    exit 1
}

Write-Host "[1/5] Found: $zipFile" -ForegroundColor Green

Write-Host "[2/5] Extracting to $InstallDir ..." -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
Expand-Archive -Path $zipFile -DestinationPath "C:\" -Force
$extracted = Get-ChildItem -Path "C:\" -Directory -Filter "mysql-*" | Select-Object -First 1
if ($extracted -and $extracted.FullName -ne $InstallDir) {
    Rename-Item -Path $extracted.FullName -NewName "mysql"
}

Write-Host "[3/5] Creating my.ini ..." -ForegroundColor Yellow
$myIni = "[mysqld]`nbasedir=$InstallDir`ndatadir=$DataDir`nport=3306`ncharacter-set-server=utf8mb4`ncollation-server=utf8mb4_unicode_ci`ndefault_authentication_plugin=mysql_native_password`nmax_connections=100`n`n[client]`ndefault-character-set=utf8mb4`nport=3306"
Set-Content -Path "$InstallDir\my.ini" -Value $myIni -Encoding UTF8

Write-Host "[4/5] Initializing MySQL (this may take a minute)..." -ForegroundColor Yellow
& "$InstallDir\bin\mysqld.exe" --initialize-insecure --console 2>&1 | ForEach-Object { Write-Host $_ }

Write-Host "[5/5] Installing Windows service..." -ForegroundColor Yellow
sc.exe delete MySQL 2>$null
Start-Sleep -Seconds 2
& "$InstallDir\bin\mysqld.exe" --install MySQL
Start-Sleep -Seconds 2
Start-Service MySQL

Start-Sleep -Seconds 3
$service = Get-Service MySQL -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  MySQL installed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Install dir: $InstallDir"
    Write-Host "  Port: 3306"
    Write-Host "  User: root"
    Write-Host "  Password: (empty)"
    Write-Host ""
    Write-Host "  Test: mysql -u root"
} else {
    Write-Host "ERROR: Service failed to start, trying manual start..." -ForegroundColor Red
    & "$InstallDir\bin\mysqld.exe" --console
}

$envPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($envPath -notlike "*$InstallDir\bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$envPath;$InstallDir\bin", "User")
    Write-Host "  Added $InstallDir\bin to PATH"
}

Write-Host ""
Write-Host "Now you can start RUCBASE:" -ForegroundColor Yellow
Write-Host "  cd c:/Users/1/CodeBuddy/20260708130302"
Write-Host "  python server/app.py"

pause
