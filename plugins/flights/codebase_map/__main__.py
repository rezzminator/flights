"""Run by `python3 -I -B {plugin}/codebase_map`: isolated mode puts only this folder on sys.path, so the package is imported from its parent."""

import os
import sys

sys.path[0] = os.path.dirname(os.path.abspath(sys.path[0]))

from codebase_map import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
