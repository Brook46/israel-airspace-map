#!/usr/bin/env python3
"""Refresh the data and publish the web app to GitHub Pages (branch gh-pages).

  python3 publish.py            # update data, then push web/ to gh-pages
  python3 publish.py --no-update
Needs a git remote 'origin' you can push to.
"""
import os, shutil, subprocess, sys, tempfile, time
import update

ROOT = os.path.dirname(os.path.abspath(__file__)); WEB = os.path.join(ROOT, 'web')


def git(*a, cwd=ROOT): return subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def main():
    if '--no-update' not in sys.argv: update.main()
    remote = git('remote', 'get-url', 'origin')
    with tempfile.TemporaryDirectory() as tmp:
        try: git('clone', '--quiet', '--depth', '1', '--branch', 'gh-pages', remote, tmp)
        except subprocess.CalledProcessError:
            git('init', '-q', '-b', 'gh-pages', cwd=tmp); git('remote', 'add', 'origin', remote, cwd=tmp)
        for f in os.listdir(tmp):
            if f != '.git': p = os.path.join(tmp, f); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        for f in os.listdir(WEB): shutil.copy2(os.path.join(WEB, f), tmp)
        open(os.path.join(tmp, '.nojekyll'), 'w').close()
        git('add', '-A', cwd=tmp)
        if not git('status', '--porcelain', cwd=tmp): print('Nothing changed.'); return
        git('commit', '-q', '-m', f'Data update {time.strftime("%Y-%m-%d %H:%M")}', cwd=tmp)
        git('push', '-q', 'origin', 'HEAD:gh-pages', cwd=tmp)
    print('Published to gh-pages.')


if __name__ == '__main__':
    main()
