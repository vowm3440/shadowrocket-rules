from pathlib import Path
import shutil
import subprocess
import unittest


class NativeResponseScriptTests(unittest.TestCase):
    def test_response_behavior_and_fail_open(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for response filter regression checks")
        result = subprocess.run([node, str(Path(__file__).with_name("response_filter.cjs"))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("11 response behavior checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
