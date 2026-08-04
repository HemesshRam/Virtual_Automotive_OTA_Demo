import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ecus.base.runtime_control import (
    DEFAULT_RUNTIME_CONTROL,
    load_runtime_control,
    save_runtime_control,
)


class TestRuntimeControl(unittest.TestCase):
    def test_missing_file_defaults_to_all_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ecus.base.runtime_control.Path", lambda value: Path(tmp) / value):
                self.assertEqual(DEFAULT_RUNTIME_CONTROL, load_runtime_control("gateway"))

    def test_saved_control_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ecus.base.runtime_control.Path", lambda value: Path(tmp) / value):
                save_runtime_control(
                    "cluster",
                    {
                        "heartbeat_enabled": False,
                        "diagnostics_enabled": True,
                        "programming_enabled": False,
                    },
                )

                self.assertEqual(
                    {
                        "heartbeat_enabled": False,
                        "diagnostics_enabled": True,
                        "programming_enabled": False,
                    },
                    load_runtime_control("cluster"),
                )


if __name__ == "__main__":
    unittest.main()
