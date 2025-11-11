import unittest
import sys

sys.path.append(".")


class TestMain(unittest.TestCase):
    def test_main_imports_cli(self):
        """Test that __main__ successfully imports cli."""
        import manage_agenda.__main__ as main_module
        self.assertTrue(hasattr(main_module, 'cli'))
        from manage_agenda.cli import cli
        self.assertEqual(main_module.cli, cli)

    def test_main_module_can_be_imported(self):
        """Test that __main__ module can be imported without errors."""
        try:
            import manage_agenda.__main__
            # If we get here, the import worked
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to import __main__: {e}")


if __name__ == "__main__":
    unittest.main()
