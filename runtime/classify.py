"""Path-only adapter for the unchanged upstream classifier."""
import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--view', type=Path, required=True)
args, forwarded = parser.parse_known_args()
sys.path.insert(0, str(args.source / 'software/scripts'))
import classify_p14_strained_aromatic_pi_distortivity as classifier
# Upstream hashes and renders evidence paths relative to ROOT. A per-run view
# contains read-only input/config links and copies of the four verified outputs.
# No methods, rules, thresholds, records, or frozen evidence are modified.
classifier.ROOT = args.view
sys.argv = ['upstream-classifier', *forwarded]
raise SystemExit(classifier.main())
