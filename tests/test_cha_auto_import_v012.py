"""Regression for cross-repository verifier's Python import resolution."""
import sys
import tempfile
import unittest
from pathlib import Path

from verify_cha_auto_route_v012 import get_cha_router


class AutoRouterImportTests(unittest.TestCase):
    def test_verifier_registers_sibling_cha_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "ski_runtime_v011.py").write_text(
                "def marker(): return 'available'\n", encoding="utf-8")
            (root / "ski_auto_route_v012.py").write_text(
                "def check():\n"
                "    from ski_runtime_v011 import marker\n"
                "    return marker()\n", encoding="utf-8")
            try:
                loaded = get_cha_router(root)
                self.assertEqual(loaded.check(), "available")
                self.assertEqual(sys.path[0], str(root))
            finally:
                if str(root) in sys.path:
                    sys.path.remove(str(root))
                # Restore the normal import environment.
                if "ski_runtime_v011" in sys.modules:
                    module = sys.modules["ski_runtime_v011"]
                    if getattr(module, "__file__", None) == str(root / "ski_runtime_v011.py"):
                        del sys.modules["ski_runtime_v011"]

    def test_missing_companion_module_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "ski_auto_route_v012.py").write_text(
                "pass\n", encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, "AUTO_ROUTE_NOT_FOUND"):
                get_cha_router(directory)


if __name__ == "__main__":
    unittest.main()
