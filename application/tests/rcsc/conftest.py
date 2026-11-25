import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'research' / 'rcsc' / 'nexus_rcsc'
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
