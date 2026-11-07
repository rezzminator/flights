"""The plugin's tests; the package under test is imported from the installable plugin folder."""

import os
import sys

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "flights")
PACKAGE_DIR = os.path.join(PLUGIN_DIR, "codebase_map")
sys.path.insert(0, PLUGIN_DIR)
