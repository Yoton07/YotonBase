"""
MySQL 8.0 一键安装脚本
"""
import subprocess
import zipfile
import shutil
import os
import sys

MYSQL_VERSION = "8.0.29"
INSTALL_DIR = r"C:\mysql"
DATA_DIR = os.path.join(INSTALL_DIR, "data")
ZIP_FILE = r"D:\mysql-8.0.29-winx64.zip"

def run_cmd(cmd, **kwargs):
    print(f"  RUN: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result

print("=" * 50)
print(f"  MySQL {MYSQL_VERSION} One-Click Install")
print("=" * 50)

# 1. 查找压缩包
if not os.path.exists(ZIP_FILE):
    print(f"ERROR: {ZIP_FILE} not found!")
    input("Press Enter to exit...")
    sys.exit(1)

print(f"\n[1/5] Found: {ZIP_FILE}")

# 2. 解压
print(f"\n[2/5] Extracting to {INSTALL_DIR} ...")
if os.path.exists(INSTALL_DIR):
    shutil.rmtree(INSTALL_DIR)

with zipfile.ZipFile(ZIP_FILE, 'r') as zf:
    zf.extractall("C:\\")

# 重命名目录
extracted_dir = os.path.join("C:\\", f"mysql-{MYSQL_VERSION}-winx64")
if os.path.exists(extracted_dir):
    os.rename(extracted_dir, INSTALL_DIR)
    print(f"  Renamed {extracted_dir} -> {INSTALL_DIR}")

# 3. 创建 my.ini（使用 ASCII 编码避免 BOM 问题）
print(f"\n[3/5] Creating my.ini ...")
ini_content = f"""[mysqld]
basedir={INSTALL_DIR}
datadir={DATA_DIR}
port=3306
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default_authentication_plugin=mysql_native_password
max_connections=100

[client]
default-character-set=utf8mb4
port=3306
"""
ini_path = os.path.join(INSTALL_DIR, "my.ini")
with open(ini_path, 'w', encoding='ascii') as f:
    f.write(ini_content)
print(f"  Written: {ini_path}")

# 4. 初始化 MySQL
print(f"\n[4/5] Initializing MySQL (this may take a minute)...")
mysqld = os.path.join(INSTALL_DIR, "bin", "mysqld.exe")
result = subprocess.run([mysqld, "--initialize-insecure", "--console"],
                        capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(result.stderr)

# 5. 安装 Windows 服务并启动
print(f"\n[5/5] Installing Windows service...")
subprocess.run(["sc", "delete", "MySQL"], capture_output=True)
import time
time.sleep(2)

result = subprocess.run([mysqld, "--install", "MySQL"], capture_output=True, text=True)
print(result.stdout or result.stderr)
time.sleep(2)

subprocess.run(["sc", "start", "MySQL"], capture_output=True)
time.sleep(3)

# 验证
result = subprocess.run(["sc", "query", "MySQL"], capture_output=True, text=True)
if "RUNNING" in result.stdout:
    print(f"\n{'=' * 50}")
    print(f"  MySQL installed successfully!")
    print(f"{'=' * 50}")
    print(f"\n  Install dir: {INSTALL_DIR}")
    print(f"  Port: 3306")
    print(f"  User: root")
    print(f"  Password: (empty)")
    print(f"\n  Test connection: mysql -u root")
    print(f"\n  Now start YotonBase:")
    print(f"    cd c:/Users/1/CodeBuddy/20260708130302")
    print(f"    python server/app.py")
else:
    print(f"\nERROR: Service may have failed to start.")
    print(result.stdout)

# 添加 PATH
try:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
    try:
        path, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        path = ""
    bin_dir = os.path.join(INSTALL_DIR, "bin")
    if bin_dir not in path:
        new_path = path + ";" + bin_dir if path else bin_dir
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        print(f"  Added {bin_dir} to PATH")
    winreg.CloseKey(key)
except Exception:
    pass

print()
input("Press Enter to exit...")
