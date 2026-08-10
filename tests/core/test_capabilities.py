import json
import unittest
from unittest import mock

from pathfinder_core import capabilities
from pathfinder_core.__main__ import main


class CapabilityTests(unittest.TestCase):
    def test_unknown_enforcement_blocks_unattended_execution(self):
        report = capabilities.probe_capabilities()
        self.assertFalse(report["unattended_execution_eligible"])
        self.assertEqual(
            report["capabilities"]["filesystem_sandbox"]["status"], "unknown"
        )

    @mock.patch("pathfinder_core.capabilities.shutil.which", return_value=None)
    def test_missing_binary_is_unavailable(self, _which):
        result = capabilities._version("missing")
        self.assertEqual(result.status, capabilities.Availability.UNAVAILABLE)

    @mock.patch("pathfinder_core.capabilities.shutil.which", return_value="/bin/tool")
    @mock.patch("pathfinder_core.capabilities.subprocess.run")
    def test_version_probe_is_bounded(self, run, _which):
        run.return_value = mock.Mock(returncode=0, stdout="tool 1.2\n", stderr="")
        result = capabilities._version("tool")
        self.assertEqual(result.status, capabilities.Availability.AVAILABLE)
        self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_json_report_is_machine_readable(self):
        report = json.loads(capabilities.capabilities_json())
        self.assertEqual(report["schema_version"], 1)
        self.assertIn("runner_available", report)

    def test_missing_datetime_validator_disables_runner(self):
        real_find_spec = capabilities.importlib.util.find_spec

        def without_datetime_validator(name):
            if name == "rfc3339_validator":
                return None
            return real_find_spec(name)

        with mock.patch(
            "pathfinder_core.capabilities.importlib.util.find_spec",
            side_effect=without_datetime_validator,
        ):
            report = capabilities.probe_capabilities()
        self.assertFalse(report["runner_available"])
        self.assertEqual(report["capabilities"]["schema_validation"]["status"], "unavailable")

    def test_doctor_json_exits_zero(self):
        with mock.patch("builtins.print") as output:
            self.assertEqual(main(["doctor", "--json"]), 0)
        self.assertTrue(output.called)


if __name__ == "__main__":
    unittest.main()
