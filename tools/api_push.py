# -*- coding: utf-8 -*-
"""Git Data API push: fallback when github.com:443 is blocked but
api.github.com still resolves (this host's daily reality).

Mirrors `git push origin master [--follow-tags]` for one commit step:
  1. git credential fill -> bearer token (same store git itself uses)
  2. git diff --raw -z --no-abbrev OLD..NEW -> changed paths
     (NUL-separated; rename rows span three NUL fields)
  3. upload blobs (base64) -> new tree on top of OLD's tree
  4. POST /git/commits with EXACT author/committer timestamps so the
     API reproduces the local commit sha bit-for-bit
  5. PATCH refs/heads/master; optionally create the annotated tag
  6. git update-ref refs/remotes/origin/master NEW (local sync)

Usage:  python tools/api_push.py [TAG]
  OLD = origin/master (remote-tracking), NEW = HEAD, TAG optional
  (e.g. `python tools/api_push.py v0.84` pushes master + that tag).
Assumes a clean worktree with everything committed.
"""
import base64
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = 'ashleymao523/fare-alert'
TAG = sys.argv[1] if len(sys.argv) > 1 else ''


def git(*a):
    r = subprocess.run(['git'] + list(a), capture_output=True)
    if r.returncode:
        raise SystemExit('git %s failed: %s' % (a[0], r.stderr.decode(errors='replace')))
    return r.stdout


def must_clean():
    st = git('status', '--porcelain').decode().strip()
    if st:
        raise SystemExit('worktree not clean:\n' + st)


must_clean()
OLD = git('rev-parse', 'origin/master').decode().strip()
NEW = git('rev-parse', 'HEAD').decode().strip()
print('pushing', OLD[:7], '->', NEW[:7], ('tag ' + TAG) if TAG else '(no tag)')
if OLD == NEW:
    raise SystemExit('origin/master already at HEAD, nothing to push')

cred = subprocess.run(['git', 'credential', 'fill'],
                      input=b'protocol=https\nhost=github.com\n\n',
                      capture_output=True).stdout.decode()
tok = [l.split('=', 1)[1].strip() for l in cred.splitlines()
       if l.startswith('password=')][0]


def api(path, data=None, method=None):
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
        data=(json.dumps(data).encode() if data is not None else None),
        method=method, headers={'Authorization': 'Bearer ' + tok,
                                'Accept': 'application/vnd.github+json',
                                'User-Agent': 'fare-alert-api-push'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')[:300]
        raise SystemExit('API %s %s -> %s %s' % (method or 'GET', path, e.code, body))


old_tree = git('rev-parse', OLD + '^{tree}').decode().strip()
raw = git('diff', '--raw', '-z', '--no-abbrev', OLD, NEW).decode('utf-8').split('\0')
entries, i = [], 0
while i + 1 < len(raw):
    words = raw[i].split()
    if not words:
        i += 2
        continue
    st, newsha = words[4], words[3]
    if 'R' in st or 'C' in st:            # old\0new\0 - three NUL fields
        oldp, path = raw[i + 1], raw[i + 2]
        entries.append({'path': oldp, 'mode': '100644', 'type': 'blob',
                        'sha': None})
        i += 3
    else:
        path = raw[i + 1]
        i += 2
    if 'D' in st[0]:
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})
    else:
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': newsha})
        blob = git('cat-file', 'blob', newsha)
        up = api('/git/blobs', {'content': base64.b64encode(blob).decode(),
                                'encoding': 'base64'}, 'POST')
        if up.get('sha') != newsha:
            raise SystemExit('blob sha mismatch for ' + path)
print('blobs+deletes:', len(entries))
tree = api('/git/trees', {'base_tree': old_tree, 'tree': entries}, 'POST')
print('new tree:', tree.get('sha'))

cobj = git('cat-file', 'commit', NEW).decode('utf-8')
head, msg = cobj.split('\n\n', 1)
parents = [l.split()[1] for l in head.splitlines() if l.startswith('parent ')]


def _who(kind):
    line = [l for l in head.splitlines() if l.startswith(kind + ' ')][0]
    body = line[len(kind) + 1:]
    name, rest = body.rsplit(' <', 1)
    email, ts, tz = rest.rsplit(' ', 2)
    email = email.rstrip('>')
    sign = 1 if tz[0] == '+' else -1
    dt_ = datetime.datetime.fromtimestamp(int(ts), datetime.timezone(datetime.timedelta(
        hours=sign * int(tz[1:3]), minutes=sign * int(tz[3:5]))))
    return {'name': name, 'email': email, 'date': dt_.isoformat()}


commit = api('/git/commits', {
    'message': msg, 'tree': tree['sha'], 'parents': parents,
    'author': _who('author'), 'committer': _who('committer')}, 'POST')
print('api commit:', commit.get('sha'))
if commit.get('sha') != NEW:
    raise SystemExit('COMMIT SHA MISMATCH api=%s local=%s' % (commit.get('sha'), NEW))
api('/git/refs/heads/master', {'sha': NEW, 'force': False}, 'PATCH')
print('master pushed', NEW)

if TAG:
    tobj = git('cat-file', 'tag', TAG).decode('utf-8')
    thead, tmsg = tobj.split('\n\n', 1)
    tlines = {l.split(' ', 1)[0]: l.split(' ', 1)[1] for l in thead.splitlines() if ' ' in l}
    tagger_raw = tlines.get('tagger', '')
    tn, rest = tagger_raw.rsplit(' <', 1)
    temail, tts, ttz = rest.rsplit(' ', 2)
    temail = temail.rstrip('>')
    sign = 1 if ttz[0] == '+' else -1
    tdt = datetime.datetime.fromtimestamp(int(tts), datetime.timezone(datetime.timedelta(
        hours=sign * int(ttz[1:3]), minutes=sign * int(ttz[3:5]))))
    apitag = api('/git/tags', {'tag': tlines['tag'], 'message': tmsg,
        'object': tlines['object'], 'type': 'commit',
        'tagger': {'name': tn, 'email': temail, 'date': tdt.isoformat()}}, 'POST')
    local_tag_sha = git('rev-parse', TAG).decode().strip()
    print('api tag:', apitag.get('sha'), 'local:', local_tag_sha)
    if apitag.get('sha') != local_tag_sha:
        raise SystemExit('TAG SHA MISMATCH')
    try:
        api('/git/refs', {'ref': 'refs/tags/' + TAG, 'sha': local_tag_sha}, 'POST')
    except SystemExit:
        print('tag ref exists, verifying')
        cur = api('/git/ref/tags/' + TAG)
        if cur.get('object', {}).get('sha') != local_tag_sha:
            raise
    print('tag pushed', local_tag_sha)

git('update-ref', 'refs/remotes/origin/master', NEW)
print('DONE')
