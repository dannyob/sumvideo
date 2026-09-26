#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "flask",
#   "waitress",
# ]
# ///

import importlib.util
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

# A stand-in for the sumvideo command: records its arguments and writes a page
FAKE_SUMVIDEO = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
while [ $# -gt 0 ]; do
    if [ "$1" = "-o" ]; then out="$2"; fi
    shift
done
if [ -n "$out" ]; then
    echo "<html><title>Fake</title></html>" > "$out/fake-video-0101.html"
    echo "HTML page created: $out/fake-video-0101.html"
fi
"""


class TestSumVideoWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parent.parent / 'web' / 'sumvideo_web.py'
        spec = importlib.util.spec_from_file_location('sumvideo_web', path)
        cls.web = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.web)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        fake = tmp / 'sumvideo'
        fake.write_text(FAKE_SUMVIDEO)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.log = tmp / 'calls.log'
        os.environ['FAKE_LOG'] = str(self.log)
        self.app = self.web.create_app(sumvideo_cmd=str(fake), jobs_dir=tmp / 'jobs')
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def _wait(self, job_path):
        for _ in range(100):
            page = self.client.get(job_path).get_data(as_text=True)
            if 'Finished' in page or 'Failed' in page:
                return page
            time.sleep(0.05)
        self.fail('job did not finish')

    def test_form(self):
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('<form', page)
        self.assertIn('name="url"', page)

    def test_rejects_non_http_url(self):
        response = self.client.post('/jobs', data={'url': 'file:///etc/passwd'})
        self.assertEqual(response.status_code, 400)

    def test_job_produces_standalone_page(self):
        response = self.client.post('/jobs', data={'url': 'https://example.com/v'})
        self.assertEqual(response.status_code, 303)
        location = response.headers['Location']
        self.assertTrue(location.startswith('jobs/'), 'redirect must be relative')
        page = self._wait('/' + location)
        self.assertIn('Finished', page)
        job_id = location.split('/')[1]
        self.assertIn(f'href="{job_id}/page"', page)
        call = self.log.read_text().splitlines()[0]
        self.assertTrue(call.startswith('--standalone -o '), call)
        self.assertTrue(call.endswith(' https://example.com/v'), call)

        download = self.client.get(f'/jobs/{job_id}/page?download=1')
        self.addCleanup(download.close)
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment; filename=fake-video-0101.html',
                      download.headers['Content-Disposition'])
        self.assertIn('<title>Fake</title>', download.get_data(as_text=True))
        inline = self.client.get(f'/jobs/{job_id}/page')
        self.addCleanup(inline.close)
        self.assertNotIn('attachment', inline.headers.get('Content-Disposition', ''))

    def test_archive_option_also_publishes(self):
        response = self.client.post('/jobs', data={'url': 'https://example.com/v',
                                                   'archive': 'on'})
        self._wait('/' + response.headers['Location'])
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], '--index https://example.com/v')

    def test_failure_is_reported(self):
        fail = Path(self.tmp.name) / 'fail'
        fail.write_text('#!/bin/sh\necho "ERROR: could not download" >&2\nexit 1\n')
        fail.chmod(fail.stat().st_mode | stat.S_IXUSR)
        app = self.web.create_app(sumvideo_cmd=str(fail), jobs_dir=Path(self.tmp.name) / 'j2')
        client = app.test_client()
        response = client.post('/jobs', data={'url': 'https://example.com/v'})
        for _ in range(100):
            page = client.get('/' + response.headers['Location']).get_data(as_text=True)
            if 'Failed' in page:
                break
            time.sleep(0.05)
        self.assertIn('Failed', page)
        self.assertIn('ERROR: could not download', page)

    def test_unknown_job_is_404(self):
        self.assertEqual(self.client.get('/jobs/nope').status_code, 404)
        self.assertEqual(self.client.get('/jobs/../../etc/passwd/page').status_code, 404)


if __name__ == '__main__':
    unittest.main()
