import tempfile
import subprocess
import unittest
from pathlib import Path

from webapp_gen.backend import Paths, Settings, WebApp, WebAppManager


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.manager = WebAppManager(Paths(self.home))
        self.manager.save_settings(Settings("pl", str(self.home / "icons"), "chromium"))

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_and_generated_files(self):
        app = WebApp(
            "ChatGPT",
            "https://chatgpt.com",
            flags=["--start-maximized"],
            custom_flags="--ozone-platform=wayland",
            extensions=["uBlock"],
        )
        saved = self.manager.save_app(app)
        loaded = self.manager.load_app("ChatGPT")
        self.assertEqual(saved, loaded)
        self.assertTrue((self.manager.paths.wrapper_dir / "ChatGPT-app").stat().st_mode & 0o111)
        wrapper = self.manager.paths.wrapper_dir / "ChatGPT-app"
        subprocess.run(["bash", "-n", str(wrapper)], check=True)
        desktop = (self.manager.paths.desktop_dir / "ChatGPT.desktop").read_text()
        self.assertIn("StartupWMClass=ChatGPT", desktop)

    def test_reads_legacy_nazwa(self):
        cfg = self.manager.paths.apps_config_dir / "Legacy.cfg"
        cfg.write_text('NAZWA="Legacy"\nURL="https://example.com"\nFLAGS=""\n')
        self.assertEqual(self.manager.load_app("Legacy").name, "Legacy")

    def test_rejects_unsafe_name(self):
        with self.assertRaises(ValueError):
            self.manager.save_app(WebApp("bad name", "https://example.com"))

    def test_remove_keeps_profile_by_default(self):
        self.manager.save_app(WebApp("Demo", "https://example.com"))
        profile = self.home / ".config/Demo-app"
        profile.mkdir()
        self.manager.remove_app("Demo")
        self.assertTrue(profile.exists())
        self.assertFalse((self.manager.paths.apps_config_dir / "Demo.cfg").exists())

    def test_special_characters_round_trip_without_shell_expansion(self):
        url = 'https://example.com/?q=$HOME&x="quoted"'
        self.manager.save_app(WebApp("Safe", url))
        self.assertEqual(self.manager.load_app("Safe").url, url)
        cfg = (self.manager.paths.apps_config_dir / "Safe.cfg").read_text()
        self.assertIn(r"\$HOME", cfg)
        output = subprocess.run(
            ["bash", "-c", f'source "$1"; printf %s "$URL"', "_", str(self.manager.paths.apps_config_dir / "Safe.cfg")],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(output, url)

    def test_refresh_launchers_uses_new_chromium_command(self):
        self.manager.save_app(WebApp("Demo", "https://example.com"))
        self.manager.save_settings(Settings("pl", "", "/opt/chromium"))
        self.manager.refresh_launchers()
        wrapper = (self.manager.paths.wrapper_dir / "Demo-app").read_text()
        self.assertIn("exec /opt/chromium", wrapper)


if __name__ == "__main__":
    unittest.main()
