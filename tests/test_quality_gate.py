"""Test installer preservation and bootstrap inside an agent runtime."""

import os
from pathlib import Path
import shutil
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
        self.git(self.repo, "init", "-q")
        self.git(self.repo, "config", "user.name", "Fixture")
        self.git(self.repo, "config", "user.email", "fixture@example.invalid")

    def git(self, repo, *arguments):
        return subprocess.check_output(
            ["git", *arguments], cwd=repo, stderr=subprocess.PIPE, text=True
        ).strip()

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)


class BootstrapTests(RepositoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        for args in [("init", "-q"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")]:
            self.git(self.upstream, *args)
        (self.upstream / "scripts").mkdir()
        (self.upstream / "scripts/setup-tools.sh").write_text(
            '#!/bin/bash\nset -eu\nmkdir -p "$1/bin"\n'
            'printf "#!/bin/sh\\nexit 0\\n" > "$1/bin/gauntlet"\n'
            'chmod +x "$1/bin/gauntlet"\n'
            'printf "%s\\n" "$1" > "$BOOTSTRAP_LOG"\n'
            'exit "${BOOTSTRAP_EXIT:-0}"\n'
        )
        self.git(self.upstream, "add", ".")
        self.git(self.upstream, "commit", "-qm", "setup fixture")
        revision = self.git(self.upstream, "rev-parse", "HEAD")
        self.write("gauntlet-version.txt", revision + "\n")
        (self.repo / "scripts").mkdir()
        shutil.copyfile(ROOT / "scripts/setup-quality-tools.sh",
                        self.repo / "scripts/setup-quality-tools.sh")
        self.env["UPSTREAM_FIXTURE"] = str(self.upstream)
        self.env["BOOTSTRAP_LOG"] = str(self.root / "bootstrap.log")
        self.env["REAL_GIT"] = shutil.which("git")
        self.executable("git", '''#!/usr/bin/env python3
import os, sys
args = [os.environ['UPSTREAM_FIXTURE'] if arg ==
        'https://github.com/matheuseabra/gauntlet-cli.git' else arg for arg in sys.argv[1:]]
os.execv(os.environ['REAL_GIT'], [os.environ['REAL_GIT'], *args])
''')

    def bootstrap(self):
        return subprocess.run(
            ["bash", str(self.repo / "scripts/setup-quality-tools.sh")],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )

    def test_setup_runs_inside_agent_checkout_and_keeps_installed_tool(self):
        result = self.bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = self.repo / ".gauntlet/tools"
        self.assertEqual(Path(self.env["BOOTSTRAP_LOG"]).read_text().strip(), str(expected))
        self.assertTrue((expected / "bin/gauntlet").is_file())

    def test_setup_failure_propagates(self):
        self.env["BOOTSTRAP_EXIT"] = "7"
        self.assertEqual(self.bootstrap().returncode, 7)

    def test_invalid_pin_fails_before_installation(self):
        self.write("gauntlet-version.txt", "main\n")
        self.assertEqual(self.bootstrap().returncode, 4)
        self.assertFalse(Path(self.env["BOOTSTRAP_LOG"]).exists())


class InstallerTests(RepositoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.env["SOURCE_REPO"] = str(ROOT)
        self.executable("npx", '#!/bin/sh\nexit "${NPX_EXIT:-0}"\n')
        self.executable("curl", '''#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
relative = sys.argv[2].split('/main/', 1)[1]
shutil.copyfile(Path(os.environ['SOURCE_REPO']) / relative, sys.argv[4])
''')

    def install(self):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/install-cloud-factory.sh")],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )

    def test_installs_integration_and_preserves_existing_configuration(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.repo / "gauntlet.toml").read_bytes(),
                         (ROOT / "templates/gauntlet.toml").read_bytes())
        self.assertTrue((self.repo / "scripts/setup-quality-tools.sh").is_file())
        self.assertEqual((self.repo / "gauntlet-version.txt").read_bytes(),
                         (ROOT / "gauntlet-version.txt").read_bytes())
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
    def test_live_workflows_match_installable_templates_and_tool_pin(self):
        for name in ("quality-gate.yml", "implement-ready-issues.yml"):
            self.assertEqual((ROOT / ".github/workflows" / name).read_bytes(),
                             (ROOT / "templates/github/workflows" / name).read_bytes())
        revision = (ROOT / "gauntlet-version.txt").read_text().strip()
        self.assertRegex(revision, r"^[0-9a-f]{40}$")
        workflow = (ROOT / ".github/workflows/quality-gate.yml").read_text()
        self.assertIn("uses: matheuseabra/gauntlet-cli@" + revision, workflow)


if __name__ == "__main__":
    unittest.main()
