import sys
import os

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Run vamos.main as a module
from amitools.tools import vamos

if __name__ == "__main__":
    vamos.main()
