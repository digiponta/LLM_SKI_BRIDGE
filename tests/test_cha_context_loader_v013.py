"""Verify the v0.13 cross-repo loader can resolve sibling CHA modules."""
import tempfile
import unittest
from pathlib import Path

from verify_cha_context_v013 import get_context_module


class ContextModuleLoaderTests(unittest.TestCase):
    def test_load_from_explicit_cha_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ski_runtime_v011.py").write_text("value = 1\n", encoding="utf-8")
            (root / "ski_auto_route_v012.py").write_text("value = 2\n", encoding="utf-8")
            (root / "ski_context_route_v013.py").write_text(
                "def context_version(): return 13\n", encoding="utf-8")
            mod = get_context_module(root)
            self.assertEqual(mod.context_version(), 13)

    def test_required_sibling_check(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ski_context_route_v013.py").write_text("pass\n", encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, "CONTEXT_MODULE_MISSING"):
                get_context_module(root)


if __name__ == "__main__":
    unittest.main()
