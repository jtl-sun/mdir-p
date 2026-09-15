import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows native preview and thumbnails')
class NativePreviewIntegrationTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('native_preview_scenario.py')), scenario],
            capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Tcl_AsyncDelete', result.stderr)
        self.assertNotIn('Exception ignored', result.stderr)

    def test_preview_after_thumbnails_renders_and_keeps_loading(self):
        self.run_scenario('thumbnails-first')

    def test_thumbnails_after_preview_preserve_rendering(self):
        self.run_scenario('preview-first')

    def test_render_error_recovers_for_next_file(self):
        self.run_scenario('render-failure')

    def test_image_pdf_and_excel_native_rendering(self):
        self.run_scenario('formats')

    def test_preview_owner_thread_can_shutdown_and_restart(self):
        self.run_scenario('controller-lifecycle')

    def test_dialog_suspension_keeps_pending_image_hidden_and_preserves_zoom(self):
        self.run_scenario('modal-suspend')
