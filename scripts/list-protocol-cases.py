"""Function names first; fixed protocol IDs are secondary lookup labels."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    print((ROOT/'configs/protocol-cases-v1.json').read_text(encoding='utf-8'))
