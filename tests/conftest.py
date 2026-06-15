import sys
from pathlib import Path

# Add project root to Python path so `import tools` and `import agent` work
sys.path.insert(0, str(Path(__file__).parent.parent))
