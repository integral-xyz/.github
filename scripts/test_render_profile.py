from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from render_profile import ROOT, date_label, main, markdown


class RenderProfileTests(unittest.TestCase):
    def test_import_needs_no_profile_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(ROOT / 'scripts/render_profile.py', root / 'render_profile.py')
            result = subprocess.run(
                [sys.executable, '-c', 'import render_profile'], cwd=root,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(result.stdout, '')
            self.assertEqual({p.name for p in root.iterdir()}, {'render_profile.py'})

    def test_apostrophes_and_quotes_remain_text(self):
        self.assertEqual(markdown('Your team\'s "work"'), 'Your team\'s "work"')
        self.assertEqual(markdown('A & B <team> *work*'), 'A &amp; B &lt;team&gt; \\*work\\*')

    def test_dates_use_fixed_english_months_and_unpadded_days(self):
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for index, month in enumerate(months, start=1):
            with self.subTest(month=month):
                value = f'2026-{index:02d}-09'
                self.assertEqual(date_label(value), f'{month} 9, 2026')
                self.assertEqual(date_label(value, include_year=False), f'{month} 9')

    def test_current_rendered_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'profile', root / 'profile')
            outputs = ['README.md', *('assets/' + p.name for p in (root / 'profile/assets').glob('momentum-*.svg'))]
            before = {path: (root / 'profile' / path).read_bytes() for path in outputs}
            with redirect_stdout(io.StringIO()):
                main(root)
            after = {path: (root / 'profile' / path).read_bytes() for path in outputs}
            self.assertEqual(before, after)
            for path in outputs[1:]:
                ET.parse(root / 'profile' / path)

    def test_editable_description_with_apostrophe_renders_correctly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'profile', root / 'profile')
            source = root / 'profile/content.json'
            content = json.loads(source.read_text())
            content['description'] = "Your team's work"
            source.write_text(json.dumps(content))
            with redirect_stdout(io.StringIO()):
                main(root)
            output = (root / 'profile/README.md').read_text()
            self.assertIn("Your team's work", output)
            self.assertNotIn('&#x27;', output)


if __name__ == '__main__':
    unittest.main()
