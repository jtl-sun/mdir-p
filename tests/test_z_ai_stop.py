from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

class AIForceStopTests(unittest.TestCase):
    def test_force_stop_kills_complete_windows_process_tree(self) -> None:
        from mdir.ai.panel import force_kill_process_tree

        process = Mock()
        process.pid = 4321
        process.poll.side_effect = [None, None]

        with patch("mdir.ai.panel.subprocess.run") as run:
            force_kill_process_tree(process, platform_name="nt")

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            ["taskkill.exe", "/PID", "4321", "/T", "/F"],
        )
        process.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
