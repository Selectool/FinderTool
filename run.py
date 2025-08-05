#!/usr/bin/env python3
import subprocess
import sys
import os

if __name__ == "__main__":
    # Запускаем main.py
    os.execv(sys.executable, [sys.executable, "main.py"])
