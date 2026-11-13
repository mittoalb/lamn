"""Build the SSH command used to run a Python script (piped on stdin) on a
remote host. Shared by the poller (probe.py) and disk alerts (offenders.py).
"""
import shlex


def remote_cmd(settings):
    """Return a single shell-safe string to run on the remote host.

    SSH concatenates extra argv with spaces and runs the result through the
    user's LOGIN shell (often tcsh here). We therefore return one argv element
    that is single-quoted — both bash and csh pass single-quoted text through
    literally, after which `sh -c` handles the real parsing.

    Non-interactive SSH shells often skip conda init, so instead of
    `conda activate` we locate the env's python binary directly.
    """
    override = settings.get("remote_python_path")
    if override:
        return f"exec {shlex.quote(override)} -"

    env = settings.get("conda_env")
    fallback = settings.get("remote_python") or "python3"
    if not env:
        return f"exec {shlex.quote(fallback)} -"

    fb_q = shlex.quote(fallback)
    script = (
        'for p in '
        f'"$HOME/miniconda3/envs/{env}/bin/python" '
        f'"$HOME/anaconda3/envs/{env}/bin/python" '
        f'"$HOME/miniforge3/envs/{env}/bin/python" '
        f'"$HOME/mambaforge/envs/{env}/bin/python" '
        f'"/opt/conda/envs/{env}/bin/python" '
        f'"/opt/miniconda3/envs/{env}/bin/python"; do '
        '[ -x "$p" ] && exec "$p" -; done; '
        f'exec {fb_q} -'
    )
    # Wrap for the login shell: `sh -c '<script>'`. shlex.quote handles any
    # embedded single quotes (there shouldn't be any, but be safe).
    return f"sh -c {shlex.quote(script)}"


def ssh_argv(ip, settings):
    user = settings["ssh_user"]
    timeout = str(settings["connect_timeout"])
    opts = list(settings.get("ssh_options", []))
    return [
        "ssh", "-o", f"ConnectTimeout={timeout}", *opts,
        f"{user}@{ip}",
        remote_cmd(settings),
    ]
