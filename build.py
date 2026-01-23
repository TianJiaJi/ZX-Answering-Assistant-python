"""
项目打包脚本
支持单文件模式和目录模式
默认编译两个版本，可通过参数选择编译单个版本
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

from src.build_tools import ensure_browser_ready, get_browser_size
from src.build_tools import ensure_flet_ready, get_flet_size


def get_platform_info():
    """
    获取平台信息

    Returns:
        dict: 包含 platform 和 architecture 的字典
    """
    import platform

    # 获取操作系统
    system = platform.system().lower()
    if system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "macos"
    elif system == "linux":
        os_name = "linux"
    else:
        os_name = system

    # 获取架构
    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        arch = "x64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    elif machine in ["arm", "armv7l"]:
        arch = "arm"
    elif machine in ["i386", "i686"]:
        arch = "x86"
    else:
        arch = machine

    return {
        "platform": os_name,
        "architecture": arch
    }


def get_dist_name(mode, version, platform_info):
    """
    获取分发文件名（不含扩展名）

    Args:
        mode: 打包模式 ("onedir" 或 "onefile")
        version: 版本号
        platform_info: 平台信息字典

    Returns:
        str: 规范化的分发名称
        目录模式: "ZX-Answering-Assistant-v2.2.0-windows-x64-installer"
        单文件模式: "ZX-Answering-Assistant-v2.2.0-windows-x64-portable"
    """
    base_name = "ZX-Answering-Assistant"

    # 添加模式标识
    if mode == "onedir":
        mode_suffix = "installer"  # 目录模式，类似安装器
    else:  # onefile
        mode_suffix = "portable"   # 单文件模式，便携版

    return f"{base_name}-v{version}-{platform_info['platform']}-{platform_info['architecture']}-{mode_suffix}"


def update_version_info():
    """更新版本信息（构建日期、时间、Git提交等）"""
    try:
        # 获取当前时间
        now = datetime.now()
        build_date = now.strftime("%Y-%m-%d")
        build_time = now.strftime("%H:%M:%S")

        # 获取Git提交信息
        git_commit = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except:
            pass

        # 读取version.py文件
        version_file = Path(__file__).parent / "version.py"
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 更新构建信息
        content = content.replace('BUILD_DATE = ""', f'BUILD_DATE = "{build_date}"')
        content = content.replace('BUILD_TIME = ""', f'BUILD_TIME = "{build_time}"')
        content = content.replace('GIT_COMMIT = ""', f'GIT_COMMIT = "{git_commit}"')
        content = content.replace('BUILD_MODE = ""', 'BUILD_MODE = "release"')

        # 写回文件
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[OK] 版本信息已更新:")
        print(f"   构建日期: {build_date}")
        print(f"   构建时间: {build_time}")
        print(f"   Git提交: {git_commit}")

    except Exception as e:
        print(f"[WARN] 更新版本信息失败: {e}")


def build_project(mode="onedir", use_upx=False):
    """
    构建项目

    Args:
        mode: 打包模式，"onefile" 或 "onedir"
        use_upx: 是否使用 UPX 压缩
    """
    # 导入版本信息
    import version
    print(f"[INFO] 打包版本: {version.get_version_string()}")
    
    # 更新构建信息
    update_version_info()

    # 重新导入版本信息以获取更新后的数据
    import importlib
    importlib.reload(version)
    print(f"[INFO] 完整版本: {version.get_full_version_string()}")
    
    # 检查是否安装了PyInstaller
    try:
        import PyInstaller
        print("[OK] PyInstaller 已安装")
    except ImportError:
        print("[ERROR] PyInstaller 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller 安装完成")
    
    # 确保所有依赖已安装
    print("\n正在安装项目依赖...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # 复制Playwright浏览器到项目目录
    print("\n正在复制Playwright浏览器...")
    if not Path("playwright_browsers").exists():
        subprocess.check_call([sys.executable, "copy_browser.py"])
    else:
        print("[OK] 浏览器目录已存在，跳过复制")
    
    # 获取Playwright安装路径
    try:
        from playwright.sync_api import sync_playwright
        print("\n[INFO] 正在获取Playwright浏览器路径...")
        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
            print(f"[OK] Playwright浏览器路径: {browser_path}")
    except Exception as e:
        print(f"[WARN] 获取Playwright路径失败: {e}")
    
    # 打包项目
    mode_name = "单文件" if mode == "onefile" else "目录模式"
    print(f"\n[INFO] 正在打包项目（{mode_name}）...")

    # 检查是否使用 UPX 压缩
    if use_upx:
        print("[INFO] UPX 压缩已启用（这将减小体积但会稍慢）")
        # 检查 UPX 是否可用
        try:
            subprocess.run(["upx", "--version"], capture_output=True, check=True)
            print("[OK] UPX 已安装并可用")
            # PyInstaller 会自动检测并使用 PATH 中的 UPX，无需额外参数
            upx_args = []
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[WARN] UPX 未安装，将跳过压缩")
            print("[INFO] 安装 UPX: https://upx.github.io/")
            # 使用 --noupx 显式禁用 UPX
            upx_args = ["--noupx"]
    else:
        # 显式禁用 UPX
        upx_args = ["--noupx"]

    cmd = [
        "pyinstaller",
        f"--{mode}",
        "--clean",
        "--noconfirm",
        "--add-data", "src" + os.pathsep + "src",
        "--add-data", "playwright_browsers" + os.pathsep + "playwright_browsers",
        "--add-data", "flet_browsers/unpacked" + os.pathsep + "flet_browsers/unpacked",
        "--add-data", "version.py" + os.pathsep + ".",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "playwright._impl._api_types",
        "--hidden-import", "playwright._impl._browser",
        "--hidden-import", "playwright._impl._connection",
        "--hidden-import", "playwright._impl._helper",
        "--hidden-import", "playwright._impl._page",
        "--hidden-import", "playwright._impl._element_handle",
        "--hidden-import", "playwright._impl._js_handle",
        "--hidden-import", "greenlet",
        "--hidden-import", "loguru",
        "--hidden-import", "yaml",
        "--hidden-import", "openpyxl",
        "--hidden-import", "aiohttp",
        "--hidden-import", "tqdm",
        "--hidden-import", "keyboard",
        "--hidden-import", "requests",
        "--hidden-import", "flet",
        "--collect-all", "playwright",
        "--collect-all", "pyyaml",
        "--collect-all", "openpyxl",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "openpyxl",
        "--exclude-module", "loguru",
        "--exclude-module", "aiohttp",
        "--exclude-module", "tqdm",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--name", "ZX-Answering-Assistant",
        "main.py"
    ]

    # 添加 UPX 参数（如果有）
    cmd.extend(upx_args)

    print("[CMD] " + " ".join(cmd))
    subprocess.check_call(cmd)

    # 输出结果
    print("\n" + "=" * 60)
    print("[OK] 项目打包完成！")
    print("=" * 60)

    if mode == "onefile":
        exe_path = Path.cwd() / 'dist' / 'ZX-Answering-Assistant.exe'
        print(f"[DIR] 可执行文件位于: {exe_path}")
        print(f"[FILE] 版本: {version.get_full_version_string()}")
        print("\n" + "=" * 60)
        print("[LIST] 使用说明:")
        print("=" * 60)
        print("[STAR] 零依赖运行：已包含Playwright浏览器，无需下载")
        print("1. 首次运行可执行文件时，会自动解压到临时目录")
        print("2. Playwright浏览器已内置，无需下载")
        print("3. Flet可执行文件已内置，首次启动无需从GitHub下载")
        print("4. 建议将可执行文件放在单独的目录中运行")
        print("5. 首次启动可能需要1-2分钟（解压文件）")
    else:
        exe_path = Path.cwd() / 'dist' / 'ZX-Answering-Assistant' / 'ZX-Answering-Assistant.exe'
        print(f"[DIR] 可执行文件位于: {exe_path}")
        print(f"[FILE] 版本: {version.get_full_version_string()}")
        print("\n" + "=" * 60)
        print("[LIST] 使用说明:")
        print("=" * 60)
        print("[STAR] 优化版：使用目录模式，启动速度快10-20倍")
        print("1. 运行 dist/ZX-Answering-Assistant/ZX-Answering-Assistant.exe")
        print("2. Playwright浏览器已内置，无需下载")
        print("3. Flet可执行文件已内置，首次启动无需从GitHub下载")
        print(f"4. 可以将整个 {dist_name} 文件夹分发给用户")
        print("5. 首次启动几乎秒开（无需解压）")

    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="ZX Answering Assistant - 项目打包工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build.py                    # 编译两个版本（onedir + onefile）
  python build.py --mode onefile     # 仅编译单文件版本
  python build.py --mode onedir      # 仅编译目录版本
  python build.py --copy-browser     # 仅复制浏览器
  python build.py --copy-all         # 复制所有依赖

输出文件名格式:
  目录模式: ZX-Answering-Assistant-v2.2.0-windows-x64-installer/
  单文件:   ZX-Answering-Assistant-v2.2.0-windows-x64-portable.exe

说明:
  - installer: 目录模式，启动快，推荐使用
  - portable: 单文件模式，所有文件打包到一个可执行文件

体积优化:
  python build.py --upx             # 启用 UPX 压缩（减小 30-50%% 体积）
  python build.py --upx --mode onefile  # 压缩单文件版本

  UPX 下载: https://upx.github.io/
  Windows: 下载 upx-4.2.2-win64.zip，解压后将 upx.exe 添加到 PATH
        """
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['onefile', 'onedir', 'both'],
        default='both',
        help='打包模式: onefile(单文件), onedir(目录模式), both(两个版本，默认)'
    )

    parser.add_argument(
        '--copy-browser',
        action='store_true',
        help='仅复制Playwright浏览器到项目目录（不进行打包）'
    )

    parser.add_argument(
        '--copy-flet',
        action='store_true',
        help='仅下载Flet可执行文件到项目目录（不进行打包）'
    )

    parser.add_argument(
        '--copy-all',
        action='store_true',
        help='复制所有依赖（Playwright浏览器 + Flet）到项目目录（不进行打包）'
    )

    parser.add_argument(
        '--force-copy',
        action='store_true',
        help='强制重新复制（覆盖已有文件）'
    )

    parser.add_argument(
        '--upx',
        action='store_true',
        help='使用 UPX 压缩可执行文件（减小 30-50%% 体积，但启动稍慢）'
    )

    parser.add_argument(
        '--no-upx',
        action='store_true',
        help='禁用 UPX 压缩（即使安装了 UPX 也不使用）'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ZX Answering Assistant - 项目打包工具")
    print("=" * 60)
    print(f"[INFO] 打包模式: {args.mode}")
    
    # 构建项目
    build_project(mode=args.mode)


if __name__ == "__main__":
    main()
