"""
Remote "top offenders" scanner. Executed over SSH by lamn.alerts (piped via
stdin) only when a disk-usage alert fires — never on the regular poll.

The server appends a line `main(<mountpoint>, <depth>, <top>, <timeout>)` to
this source before sending it. Prints a single JSON document to stdout:

    {"mountpoint": "/data", "offenders": [{"path", "size", "owner"}, ...],
     "partial": bool, "unreadable": bool, "error": str|None}

Uses GNU `du -x` (stays on the one filesystem). Runs as the SSH user, so
directories that user cannot read are under-counted ("unreadable": true).
Must stay Python 3.6 compatible and stdlib-only.
"""
import json
import os
import pwd
import stat
import subprocess
import sys


def _owner(path):
    try:
        uid = os.lstat(path).st_uid
    except OSError:
        return "?"
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _is_dir(path):
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def _depth(path, root):
    rel = os.path.relpath(path, root)
    return 0 if rel == "." else rel.count(os.sep) + 1


def main(mountpoint, depth=1, top=5, timeout=600):
    result = {"mountpoint": mountpoint, "offenders": [], "partial": False,
              "unreadable": False, "error": None}
    cmd = ["du", "-x", "-a", "-0", "-B1", "--max-depth=%d" % depth,
           "--", mountpoint]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except OSError as e:
        result["error"] = "cannot run du: %s" % e
        _emit(result)
        return

    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        result["partial"] = True
    if not result["partial"] and proc.returncode != 0:
        result["unreadable"] = True

    entries = []
    for rec in out.split(b"\0"):
        if b"\t" not in rec:
            continue
        size, path = rec.split(b"\t", 1)
        path = os.fsdecode(path)
        d = _depth(path, mountpoint)
        if d == 0:
            continue
        # Keep a non-overlapping set: entries at the target depth, plus
        # files that sit shallower (they have no children to double-count).
        if d < depth and _is_dir(path):
            continue
        try:
            entries.append((int(size), path))
        except ValueError:
            continue

    entries.sort(reverse=True)
    result["offenders"] = [
        {"path": p, "size": s, "owner": _owner(p)} for s, p in entries[:top]
    ]
    _emit(result)


def _emit(result):
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
