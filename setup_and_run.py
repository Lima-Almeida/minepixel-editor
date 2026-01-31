#!/usr/bin/env python3
"""
Minepixel Editor - Universal Setup and Run Script
Works on Windows, Linux, and macOS
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def print_header():
    """Print welcome header."""
    print("=" * 50)
    print("Minepixel Editor - Setup and Run")
    print("=" * 50)
    print()


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version < (3, 8):
        print(f"[ERROR] Python 3.8+ requerido. Você tem Python {version.major}.{version.minor}")
        sys.exit(1)
    print(f"[INFO] Python {version.major}.{version.minor}.{version.micro} encontrado!")


def get_venv_paths():
    """Get virtual environment paths based on OS."""
    venv_dir = Path("venv")
    
    if platform.system() == "Windows":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
    
    return venv_dir, python_exe, pip_exe


def create_venv():
    """Create virtual environment if it doesn't exist."""
    venv_dir, python_exe, _ = get_venv_paths()
    
    if not venv_dir.exists():
        print("[INFO] Criando ambiente virtual...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print("[OK] Ambiente virtual criado!")
        except subprocess.CalledProcessError:
            print("[ERROR] Falha ao criar ambiente virtual.")
            print("Tente instalar: python -m pip install virtualenv")
            sys.exit(1)
    else:
        print("[INFO] Ambiente virtual já existe.")
    
    return python_exe, venv_dir


def install_dependencies(python_exe):
    """Install project dependencies."""
    print("[INFO] Atualizando pip...")
    try:
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print("[WARNING] Falha ao atualizar pip, continuando...")
    
    print("[INFO] Instalando dependências...")
    try:
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("[OK] Dependências instaladas!")
    except subprocess.CalledProcessError:
        print("[ERROR] Falha ao instalar dependências.")
        sys.exit(1)


def run_application(python_exe):
    """Run the main application."""
    print()
    print("[INFO] Iniciando Minepixel Editor...")
    print()
    
    try:
        # Run in same console/terminal
        result = subprocess.run([str(python_exe), "main.py"])
        return result.returncode
    except KeyboardInterrupt:
        print("\n[INFO] Aplicação interrompida pelo usuário.")
        return 0
    except Exception as e:
        print(f"[ERROR] Erro ao executar aplicação: {e}")
        return 1


def main():
    """Main entry point."""
    print_header()
    
    # Check Python version
    check_python_version()
    print()
    
    # Create virtual environment
    python_exe, venv_dir = create_venv()
    print()
    
    # Install dependencies
    install_dependencies(python_exe)
    print()
    
    # Run application
    exit_code = run_application(python_exe)
    
    # Handle errors
    if exit_code != 0:
        print()
        print("[ERROR] O programa fechou com erro.")
        if platform.system() == "Windows":
            input("Pressione Enter para continuar...")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
