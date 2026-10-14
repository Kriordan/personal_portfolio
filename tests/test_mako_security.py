"""Mako URI confinement and Alembic's use of the locked template engine."""

import ntpath
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from alembic.script import ScriptDirectory
from mako import exceptions
from mako.lookup import TemplateLookup


class MakoSecurityTests(unittest.TestCase):
    def test_windows_drive_uris_cannot_read_outside_template_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "templates"
            root.mkdir()
            (root / "ok.html").write_text("Hello ${name}", encoding="utf-8")
            (Path(directory) / "outside.txt").write_text("private fixture", encoding="utf-8")
            lookup = TemplateLookup(directories=[str(root)])

            # Exercise Windows normalization on macOS/Linux too. The actual
            # lookup and file reads remain real, limited to this temp fixture.
            with patch("mako.template.os.path", ntpath):
                self.assertEqual(lookup.get_template("ok.html").render(name="Ada"), "Hello Ada")
                for uri in (
                    "C:/../../outside.txt",
                    r"C:\..\..\outside.txt",
                    "d:/../../outside.txt",
                    "../outside.txt",
                    "//../outside.txt",
                    r"\..\outside.txt",
                ):
                    with self.subTest(uri=uri), self.assertRaises(exceptions.TemplateLookupException):
                        lookup.get_template(uri)

    def test_alembic_generates_loadable_revision_using_repository_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "versions").mkdir()
            template = Path(__file__).resolve().parents[1] / "migrations" / "script.py.mako"
            shutil.copyfile(template, root / "script.py.mako")
            scripts = ScriptDirectory(directory)
            revision = scripts.generate_revision("security_fixture", "Verify Mako compatibility", head="base")
            self.assertEqual(revision.revision, "security_fixture")
            self.assertIsNone(revision.down_revision)
            self.assertTrue(callable(revision.module.upgrade))
            self.assertTrue(callable(revision.module.downgrade))
            self.assertEqual(ScriptDirectory(directory).get_current_head(), "security_fixture")


if __name__ == "__main__":
    unittest.main()
