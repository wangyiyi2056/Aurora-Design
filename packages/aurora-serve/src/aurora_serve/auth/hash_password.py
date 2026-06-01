#!/usr/bin/env python3
"""CLI tool to hash passwords for Aurora auth.

Usage:
    python -m aurora_serve.auth.hash_password <password>
    python -m aurora_serve.auth.hash_password   # prompts interactively
"""
from __future__ import annotations

import getpass
import sys

import bcrypt


def main() -> None:
    if len(sys.argv) < 2:
        password = getpass.getpass("Enter password: ")
    else:
        password = sys.argv[1]

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    print(f"Hash: {hashed}")


if __name__ == "__main__":
    main()
