#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "flask",
#   "waitress",
# ]
# ///
"""A small web front end for sumvideo.

Paste a video URL and get back a standalone HTML page. Optionally also publish
the video to the sumvideo archive directory and rebuild its index.

It runs the installed `sumvideo` command, one job at a time, and is meant to
listen on localhost behind something that restricts access (e.g. `tailscale
serve`). All links are relative, so it can be mounted under a path prefix.

Environment:
    SUMVIDEO_WEB_PORT   port to listen on (default 8765)
    SUMVIDEO_WEB_JOBS   directory for job output (default ~/.cache/sumvideo-web)
    SUMVIDEO_CMD        sumvideo command to run (default: sumvideo on PATH)
"""
import html
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from flask import Flask, abort, redirect, request, send_file
from werkzeug.exceptions import NotFound

PAGE_CREATED = re.compile(r'^HTML page created: (.+)$', re.MULTILINE)
MAX_LOG_LINES = 15
JOB_MAX_AGE = 24 * 3600  # seconds to keep finished job output

STYLE = """
    :root { --bg: #fafaf8; --fg: #1f2328; --muted: #656d76; --rule: #e4e4e0;
            --panel: #f1f1ed; --accent: #0b62c4; --on-accent: #fff; --bad: #b3261e; }
    @media (prefers-color-scheme: dark) {
        :root { --bg: #16181b; --fg: #e6e6e3; --muted: #9aa0a6; --rule: #2c2f33;
                --panel: #1f2226; --accent: #6aa8f0; --on-accent: #0d1117; --bad: #f2b8b5; }
    }
    * { box-sizing: border-box; }
    body { max-width: 720px; margin: 0 auto; padding: 32px 20px; background: var(--bg);
           color: var(--fg); font: 17px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
           Roboto, "Helvetica Neue", Arial, sans-serif; }
    h1 { font-size: 1.5rem; margin: 0 0 20px; }
    a { color: var(--accent); }
    form { display: grid; gap: 12px; }
    input[type=url] { font: inherit; padding: 10px 12px; border: 1px solid var(--rule);
                      border-radius: 6px; background: var(--panel); color: var(--fg); width: 100%; }
    button, .button { font: inherit; font-weight: 600; padding: 8px 16px; border: none;
                      border-radius: 6px; background: var(--accent); color: var(--on-accent);
                      cursor: pointer; text-decoration: none; display: inline-block; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .failed { color: var(--bad); }
    pre { background: var(--panel); padding: 12px; border-radius: 6px; font-size: 0.8rem;
          overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
    ul { padding-left: 1.2em; }
    li { margin: 4px 0; overflow-wrap: anywhere; }
"""


@dataclass
class Job:
    """One request to turn a URL into a standalone page."""
    id: str
    url: str
    archive: bool
    directory: Path
    status: str = 'Queued'  # Queued, Running, Finished or Failed
    log: list[str] = field(default_factory=list)
    page: Path | None = None
    created: float = field(default_factory=time.time)


class JobRunner:
    """Runs sumvideo jobs one at a time on a background thread."""

    def __init__(self, sumvideo_cmd: str, jobs_dir: Path) -> None:
        self.sumvideo_cmd = sumvideo_cmd
        self.jobs_dir = jobs_dir
        self.jobs: dict[str, Job] = {}
        self.queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def submit(self, url: str, archive: bool) -> Job:
        self._remove_old_jobs()
        job_id = uuid.uuid4().hex
        directory = self.jobs_dir / job_id
        directory.mkdir(parents=True)
        job = Job(id=job_id, url=url, archive=archive, directory=directory)
        self.jobs[job_id] = job
        self.queue.put(job)
        return job

    def recent(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda job: job.created, reverse=True)[:10]

    def _work(self) -> None:
        while True:
            self._run(self.queue.get())

    def _run(self, job: Job) -> None:
        job.status = 'Running'
        ok, output = self._sumvideo(job, ['--standalone', '-o', str(job.directory), job.url])
        match = PAGE_CREATED.search(output)
        if ok and match:
            page = Path(match.group(1).strip()).resolve()
            if page.is_relative_to(job.directory.resolve()) and page.exists():
                job.page = page
        if ok and job.page and job.archive:
            ok, _ = self._sumvideo(job, ['--index', job.url])
        job.status = 'Finished' if ok and job.page else 'Failed'

    def _sumvideo(self, job: Job, args: list[str]) -> tuple[bool, str]:
        """Run sumvideo, keeping the last few output lines on the job for the status page."""
        job.log.append(f"$ sumvideo {' '.join(args)}")
        output = []
        try:
            process = subprocess.Popen([self.sumvideo_cmd, *args], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors='replace')
        except OSError as e:
            job.log.append(f"could not run sumvideo: {e}")
            return False, ""
        with process:
            assert process.stdout is not None
            for chunk in process.stdout:
                output.append(chunk)
                # yt-dlp redraws progress with \r; keep only the latest state of each line
                line = chunk.rstrip('\n').split('\r')[-1].strip()
                if line:
                    job.log[:] = [*job.log, line][-MAX_LOG_LINES:]
        return process.returncode == 0, ''.join(output)

    def _remove_old_jobs(self) -> None:
        cutoff = time.time() - JOB_MAX_AGE
        for job_id, job in list(self.jobs.items()):
            if job.created < cutoff and job.status in ('Finished', 'Failed'):
                shutil.rmtree(job.directory, ignore_errors=True)
                del self.jobs[job_id]


def page(title: str, body: str, refresh: bool = False) -> str:
    meta = '<meta http-equiv="refresh" content="2">' if refresh else ''
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">{meta}
<title>{html.escape(title)}</title><style>{STYLE}</style></head>
<body>{body}</body></html>"""


def create_app(sumvideo_cmd: str = 'sumvideo', jobs_dir: Path | None = None) -> Flask:
    app = Flask(__name__)
    runner = JobRunner(sumvideo_cmd, jobs_dir or Path.home() / '.cache' / 'sumvideo-web')

    @app.get('/')
    def index() -> str:
        jobs = ''.join(
            f'<li><a href="jobs/{job.id}">{html.escape(job.url)}</a> '
            f'<span class="muted">{job.status}</span></li>' for job in runner.recent())
        return page('sumvideo', f"""
<h1>sumvideo</h1>
<form method="post" action="jobs">
  <input type="url" name="url" placeholder="https://..." required autofocus>
  <label><input type="checkbox" name="archive"> Also publish to the archive</label>
  <div><button type="submit">Make page</button></div>
</form>
{'<h2>Recent</h2><ul>' + jobs + '</ul>' if jobs else ''}""")

    @app.post('/jobs')
    def submit():
        url = request.form.get('url', '').strip()
        if not url.startswith(('http://', 'https://')):
            abort(400, 'Only http and https URLs are supported')
        job = runner.submit(url, archive=bool(request.form.get('archive')))
        return redirect(f'jobs/{job.id}', code=303)

    def get_job(job_id: str) -> Job:
        job = runner.jobs.get(job_id)
        if job is None:
            raise NotFound()
        return job

    @app.get('/jobs/<job_id>')
    def status(job_id: str) -> str:
        job = get_job(job_id)
        done = job.status in ('Finished', 'Failed')
        links = ''
        if job.page:
            links = (f'<p><a class="button" href="{job.id}/page">View page</a> '
                     f'<a class="button" href="{job.id}/page?download=1">Download</a></p>')
        published = ' and published to the archive' if job.archive and job.status == 'Finished' else ''
        css = ' class="failed"' if job.status == 'Failed' else ''
        return page(f'sumvideo: {job.status}', f"""
<h1{css}>{job.status}{published}</h1>
<p class="muted">{html.escape(job.url)}</p>
{links}
<pre>{html.escape(chr(10).join(job.log)) or 'Waiting to start...'}</pre>
<p><a href="../">Make another</a></p>""", refresh=not done)

    @app.get('/jobs/<job_id>/page')
    def result(job_id: str):
        job = get_job(job_id)
        if job.page is None:
            raise NotFound()
        return send_file(job.page, mimetype='text/html',
                         as_attachment=bool(request.args.get('download')),
                         download_name=job.page.name)

    return app


def main() -> None:
    from waitress import serve
    app = create_app(sumvideo_cmd=os.environ.get('SUMVIDEO_CMD', 'sumvideo'),
                     jobs_dir=Path(os.environ['SUMVIDEO_WEB_JOBS'])
                     if 'SUMVIDEO_WEB_JOBS' in os.environ else None)
    serve(app, host='127.0.0.1', port=int(os.environ.get('SUMVIDEO_WEB_PORT', '8765')))


if __name__ == '__main__':
    main()
