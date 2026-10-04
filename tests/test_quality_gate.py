"""Exercise committed diff selection, exit propagation, and installer behavior."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = os.environ | {"PATH": f"{self.bin}:{os.environ['PATH']}"}
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("unchanged.py", "def untouched(): return 1\n")
        self.base = self.commit()
        self.log = self.root / "arguments.json"
        self.env["ARGUMENT_LOG"] = str(self.log)
        self.executable("gauntlet", """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ['ARGUMENT_LOG']).write_text(json.dumps(sys.argv[1:]))
code = int(os.environ.get('GATE_EXIT', '0'))
result = {'version': 1, 'status': 'failed' if code else 'passed'}
Path('.gauntlet/results.json').write_text(json.dumps(result))
print(json.dumps(result))
sys.exit(code)
""")

    def git(self, *arguments):
        return subprocess.check_output(
            ["git", *arguments], cwd=self.repo, stderr=subprocess.PIPE, text=True
        ).strip()

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def gate(self, base=None, head=None):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/check-quality-gate.sh"),
             base or self.base, head or self.git("rev-parse", "HEAD")],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )

    def arguments(self):
        return json.loads(self.log.read_text())


class QualityGateTests(RepositoryFixture, unittest.TestCase):
    def test_committed_paths_preserve_unusual_names_and_ignore_deletions(self):
        names = ["src/a space.py", "src/a\nnewline.py", "-option.py"]
        for name in names:
            self.write(name, "def value(): return 2\n")
        (self.repo / "unchanged.py").unlink()
        self.commit()
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.arguments()[:5],
                         ["check", "--all", "--json", "--output", ".gauntlet/results.json"])
        self.assertCountEqual(self.arguments()[5:], [f"./{name}" for name in names])
        self.assertEqual(json.loads(result.stdout)["status"], "passed")

    def test_rename_analyzes_new_path(self):
        self.git("mv", "unchanged.py", "renamed.py")
        self.commit()
        self.assertEqual(self.gate().returncode, 0)
        self.assertEqual(self.arguments()[5:], ["./renamed.py"])

    def test_uses_merge_base_instead_of_base_tip(self):
        self.git("checkout", "-qb", "base-branch")
        self.write("base-only.py", "def unrelated(): return 1\n")
        base_tip = self.commit()
        self.git("checkout", "-qb", "feature", self.base)
        self.write("feature.py", "def feature(): return 2\n")
        self.commit()
        self.assertEqual(self.gate(base=base_tip).returncode, 0)
        self.assertEqual(self.arguments()[5:], ["./feature.py"])

    def test_empty_diff_has_explicit_empty_scope_and_cleans_it_up(self):
        self.assertEqual(self.gate().returncode, 0)
        scope = Path(self.arguments()[5])
        self.assertEqual(scope.parent, self.repo / ".gauntlet")
        self.assertFalse(scope.exists())

    def test_all_gauntlet_failure_codes_propagate_with_report(self):
        self.write("changed.py", "def changed(): return 1\n")
        self.commit()
        for code in range(1, 6):
            with self.subTest(code=code):
                self.env["GATE_EXIT"] = str(code)
                self.assertEqual(self.gate().returncode, code)
                report = json.loads((self.repo / ".gauntlet/results.json").read_text())
                self.assertEqual(report["status"], "failed")

    def test_wrong_checkout_and_dirty_tracked_tree_are_rejected(self):
        self.write("changed.py", "def changed(): return 1\n")
        self.commit()
        self.assertEqual(self.gate(head=self.base).returncode, 4)
        self.write("changed.py", "def changed(): return 2\n")
        self.assertEqual(self.gate().returncode, 4)
        self.assertFalse(self.log.exists())

    def test_missing_base_does_not_fall_back_to_full_scan(self):
        self.assertNotEqual(self.gate(base="0" * 40).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_missing_cli_removes_stale_report_and_fails(self):
        (self.bin / "gauntlet").unlink()
        self.env["PATH"] = f"{self.bin}:/usr/bin:/bin"
        self.write(".gauntlet/results.json", '{"status":"passed"}')
        self.assertEqual(self.gate().returncode, 127)
        self.assertFalse((self.repo / ".gauntlet/results.json").exists())


class InstallerTests(RepositoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.env["SOURCE_REPO"] = str(ROOT)
        self.executable("npx", "#!/bin/sh\nexit \"${NPX_EXIT:-0}\"\n")
        self.executable("curl", """#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
url = sys.argv[2]
relative = url.split('/main/', 1)[1]
shutil.copyfile(Path(os.environ['SOURCE_REPO']) / relative, sys.argv[4])
""")

    def install(self):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/install-cloud-factory.sh")],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )

    def test_installs_integration_and_preserves_existing_configuration(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.repo / "gauntlet.toml").read_bytes(),
                         (ROOT / "templates/gauntlet.toml").read_bytes())
        self.assertTrue((self.repo / "scripts/check-quality-gate.sh").is_file())
        self.assertEqual((self.repo / ".github/workflows/quality-gate.yml").read_bytes(),
                         (ROOT / "templates/github/workflows/quality-gate.yml").read_bytes())
        self.write("gauntlet.toml", "# custom configuration\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.repo / "gauntlet.toml").read_text(), "# custom configuration\n")
        self.assertEqual((self.repo / ".gitignore").read_text().count("!.gauntlet/accept.toml"), 1)

    def test_dependency_install_failure_stops_before_copying_workflows(self):
        self.env["NPX_EXIT"] = "7"
        self.assertEqual(self.install().returncode, 7)
        self.assertFalse((self.repo / ".github/workflows").exists())


class ContractTests(unittest.TestCase):
    def test_live_workflow_matches_installable_template(self):
        self.assertEqual((ROOT / ".github/workflows/quality-gate.yml").read_bytes(),
                         (ROOT / "templates/github/workflows/quality-gate.yml").read_bytes())


if __name__ == "__main__":
    unittest.main()
