"""Entry point wrapper for Nuitka onefile build.

Nuitka compiles this file as the top-level script. Importing
os_deployment.main here ensures the package context is established
before main() runs, so all relative imports inside the package work.
"""
from os_deployment.main import main

if __name__ == "__main__":
    main()
