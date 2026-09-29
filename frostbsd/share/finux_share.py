#!/usr/bin/env python3
"""finux-share: share a Finux image on your home network first, then on the internet.

    finux-share lan [IMAGE or FOLDER ...]         serve it to your home network only
    finux-share wan DEST [IMAGE or FOLDER ...]    upload it to your web server, e.g.
                                                  finux-share wan you@finux.tech:/var/www/finux

Images are what the builds make: FROSTFORPRESIDENT.img from build/build-frostbsd.sh,
FrostOS.*.iso from the SUSE variant, and .xz/.zst/.gz copies of them. With no
image named, it shares the images in the current folder.

lan  A small web server on port 45700: a download page (fine on phones and
     headsets too), SHA256SUMS, and downloads that resume after a dropped
     connection. It answers only devices on private networks (192.168.x.x,
     10.x.x.x, 172.16-31.x.x and so on), even if the port is forwarded by mistake.

wan  Writes the same page and SHA256SUMS, then copies them and the images to a
     web server with rsync, resuming big files. Serve that folder over HTTPS.
     --sign KEY signs SHA256SUMS with an SSH key (ssh-keygen -Y sign), so people
     can check an image came from you and not just from the server.

Stdlib only.
"""
import argparse
import hashlib
import html
import ipaddress
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

PORT = 45700
IMAGE_TYPES = (".img", ".iso", ".raw", ".qcow2", ".vmdk")
PACKED = (".xz", ".zst", ".gz")
NAMESPACE = "finux"             # ssh-keygen -Y signature namespace


class ShareError(Exception):
    pass


def is_image(path: Path) -> bool:
    name = path.name.lower()
    for ext in PACKED:
        if name.endswith(ext):
            name = name[:-len(ext)]
    return name.endswith(IMAGE_TYPES)


def find_images(args) -> list:
    """The image files named, plus the images in any folder named (not its subfolders)."""
    found = []
    for a in args or ["."]:
        p = Path(a).expanduser()
        if p.is_dir():
            found += sorted(q for q in p.iterdir() if q.is_file() and is_image(q))
        elif p.is_file():
            found.append(p)
        else:
            raise ShareError(f"No such file or folder: {a}")
    names = [p.name for p in found]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise ShareError("Two images have the same name: " + ", ".join(twice))
    if not found:
        raise ShareError("No Finux image here. Build one (frostbsd/build/build-frostbsd.sh), "
                         "or name it: finux-share lan FROSTFORPRESIDENT.img")
    return found


def human(n: float) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def checksums(images, say=print) -> dict:
    """SHA-256 of every image, by file name."""
    out = {}
    for p in images:
        say(f"Checking {p.name} ({human(p.stat().st_size)})…")
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[p.name] = h.hexdigest()
    return out


def sums_text(sums: dict) -> str:
    """SHA256SUMS in the format sha256sum -c and shasum -a 256 -c read."""
    return "".join(f"{digest}  {name}\n" for name, digest in sums.items())


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finux</title>
<style>
:root {{ --bg: #eef0f2; --panel: #fff; --line: #d9dde1; --text: #1d2226; --muted: #626b73; --accent: #1d7fa6; --on-accent: #fff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #15181b; --panel: #1e2226; --line: #343a40; --text: #e6e8ea; --muted: #9aa3ab; --accent: #6cc7ea; --on-accent: #15181b; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 17px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 760px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ margin: 0 0 4px; font-size: 30px; }}
h2 {{ margin: 0 0 8px; font-size: 21px; }}
ul {{ padding-left: 20px; }}
.card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 18px; margin: 16px 0; }}
a {{ color: var(--accent); }}
.dl {{ display: block; padding: 16px 18px; border-radius: 12px; background: var(--accent); color: var(--on-accent); font-weight: 600; font-size: 19px; text-decoration: none; word-break: break-all; }}
.meta {{ color: var(--muted); font-size: 14px; margin-top: 8px; }}
code {{ font: 13px/1.5 ui-monospace, "DejaVu Sans Mono", monospace; word-break: break-all; }}
pre {{ background: var(--bg); border-radius: 8px; padding: 10px 12px; overflow-x: auto; }}
.muted {{ color: var(--muted); }}
</style></head>
<body><main>
<h1>Finux</h1>
<p class="muted">FrostBSD / FrostOS: a FreeBSD-derived OS with Qoin at its core.</p>
{images}
<div class="card">
<h2>Check the download</h2>
<p>The code under each image is its SHA-256. Yours must match it exactly:</p>
<ul>
<li>Linux, FreeBSD 14: <code>sha256sum FILE</code></li>
<li>macOS: <code>shasum -a 256 FILE</code></li>
<li>Windows: <code>certutil -hashfile FILE SHA256</code></li>
</ul>
<p class="muted">All of them in one file: <a href="SHA256SUMS">SHA256SUMS</a>.</p>
{signature}
</div>
<div class="card">
<h2>Use it</h2>
<p>Try it in a virtual machine first:</p>
<pre>qemu-system-x86_64 -m 2048 -drive file=FILE,format=raw -nographic</pre>
<p>Or write it to a USB stick with balenaEtcher, or <code>dd</code>. This erases the stick:</p>
<pre>sudo dd if=FILE of=/dev/sdX bs=4M status=progress</pre>
<p class="muted">Early build: log in as root and set a password straight away.</p>
</div>
</main></body></html>
"""

IMAGE_CARD = """<div class="card">
<a class="dl" href="{href}" download>{name}</a>
<div class="meta">{size}</div>
<div class="meta">SHA-256 <code>{digest}</code></div>
</div>"""

SIGNATURE = """<p>SHA256SUMS is signed (<a href="SHA256SUMS.sig">SHA256SUMS.sig</a>). To check it, save this line as
<code>allowed_signers</code>, then run:</p>
<pre>{signer}</pre>
<pre>ssh-keygen -Y verify -f allowed_signers -I {ns} -n {ns} -s SHA256SUMS.sig &lt; SHA256SUMS</pre>
<p class="muted">Get the key line from somewhere other than this server too, such as the Finux repo, or the check proves nothing.</p>"""


def page(images, sums: dict, signer: str = "") -> str:
    """The download page."""
    cards = "".join(IMAGE_CARD.format(href=html.escape(quote(p.name)), name=html.escape(p.name),
                                      size=human(p.stat().st_size), digest=sums[p.name]) for p in images)
    signature = SIGNATURE.format(signer=html.escape(signer), ns=NAMESPACE) if signer else ""
    return PAGE.format(images=cards, signature=signature)


# ---------------------------------------------------------------------------
# lan: serve the images to this home network only.
def lan_address():
    """This computer's address on its home network, or None if it has none."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))     # picks the route out; nothing is sent
            ip = s.getsockname()[0]
        except OSError:
            return None
    a = ipaddress.ip_address(ip)
    return ip if a.is_private and not a.is_loopback else None


def nearby(ip: str) -> bool:
    """Is this client on a private network, or this computer?"""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_private or a.is_loopback or a.is_link_local


_RANGE = re.compile(r"\s*bytes\s*=\s*(\d*)-(\d*)\s*", re.ASCII | re.IGNORECASE)


def byte_range(header: str, size: int):
    """(first, last) byte for a single "bytes=" Range; None to send the whole file.
    ValueError if the range starts past the end."""
    m = _RANGE.fullmatch(header)
    if not m or not (m[1] or m[2]):         # several ranges, or nonsense: send it all
        return None
    first, last = m[1], m[2]
    if not first:                           # the last N bytes
        n = int(last)
        if n == 0:
            raise ValueError("empty range")
        return max(0, size - n), size - 1
    start, end = int(first), int(last) if last else size - 1
    if start >= size or start > end:
        raise ValueError("range starts past the end")
    return start, min(end, size - 1)


class Share:
    """What the server hands out: the page, SHA256SUMS, and the image files by name."""

    def __init__(self, images, sums: dict):
        self.files = {p.name: p for p in images}
        self.page = page(images, sums).encode()
        self.sums = sums_text(sums).encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "finux-share"
    share = None

    def log_message(self, *args):
        pass

    def do_GET(self):
        self._answer(head=False)

    def do_HEAD(self):
        self._answer(head=True)

    def _plain(self, code, body, ctype, head):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _answer(self, head):
        if not nearby(self.client_address[0]):
            return self._plain(403, b"This Finux share is for its home network only.\n", "text/plain; charset=utf-8", head)
        path = unquote(urlsplit(self.path).path).lstrip("/")
        if path in ("", "index.html"):
            return self._plain(200, self.share.page, "text/html; charset=utf-8", head)
        if path == "SHA256SUMS":
            return self._plain(200, self.share.sums, "text/plain; charset=utf-8", head)
        image = self.share.files.get(path)
        if image is None:
            return self._plain(404, b"Not here.\n", "text/plain; charset=utf-8", head)
        self._image(image, head)

    def _image(self, image, head):
        size = image.stat().st_size
        first, last, code = 0, size - 1, 200
        try:
            wanted = byte_range(self.headers.get("Range", ""), size) if self.headers.get("Range") else None
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if wanted:
            (first, last), code = wanted, 206
        self.send_response(code)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(image.name)}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(last - first + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
        self.end_headers()
        if head:
            return
        print(f"{self.client_address[0]} is downloading {image.name}"
              + (f", resuming at {human(first)}" if first else ""), flush=True)
        try:
            with open(image, "rb") as f:
                f.seek(first)
                left = last - first + 1
                while left:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                # they cancelled; a Range request picks it up again


def serve_lan(images, sums, port=PORT, bind=None):
    ip = bind or lan_address()
    Handler.share = Share(images, sums)
    try:
        srv = ThreadingHTTPServer((ip or "0.0.0.0", port), Handler)
    except OSError as e:
        raise ShareError(f"Can't listen on port {port}: {e}. Pick another with --port.")
    srv.daemon_threads = True
    where = f"http://{ip}:{srv.server_address[1]}/" if ip else f"port {srv.server_address[1]} of this computer"
    print(f"Sharing {len(images)} image{'s' if len(images) != 1 else ''} on your home network: {where}")
    print("Open that on the other computer, phone or headset. Only devices on this network get an answer.")
    print("Ctrl+C to stop.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped sharing.")
    finally:
        srv.server_close()


# ---------------------------------------------------------------------------
# wan: put the page, checksums and images on a web server.
def sign(sums_file: Path, key: str) -> str:
    """Sign SHA256SUMS with an SSH key; returns the allowed_signers line for the page."""
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        raise ShareError("--sign needs ssh-keygen (OpenSSH 8.0 or newer)")
    key = str(Path(key).expanduser())
    subprocess.run([keygen, "-Y", "sign", "-f", key, "-n", NAMESPACE, str(sums_file)], check=True)
    pub = Path(key + ".pub")
    return f"{NAMESPACE} {' '.join(pub.read_text().split()[:2])}" if pub.exists() else ""


def publish_wan(images, sums, dest: str, key=None, dry_run=False, run=subprocess.run):
    """Copy the page, SHA256SUMS (and its signature) and the images to dest with rsync."""
    rsync = shutil.which("rsync")
    if not rsync and not dry_run:
        raise ShareError("wan needs rsync. Install it (pkg install rsync, or apt install rsync) and run this again.")
    with tempfile.TemporaryDirectory(prefix="finux-share-") as tmp:
        sums_file = Path(tmp) / "SHA256SUMS"
        sums_file.write_text(sums_text(sums))
        extra = [sums_file]
        signer = ""
        if key:
            if not dry_run:                 # a dry run never asks for the key's passphrase
                signer = sign(sums_file, key)
            extra.append(Path(tmp) / "SHA256SUMS.sig")
        index = Path(tmp) / "index.html"
        index.write_text(page(images, sums, signer))
        cmd = [rsync or "rsync", "-rtv", "--partial", "--progress", "--chmod=D755,F644",
               str(index), *map(str, extra), *map(str, images), dest.rstrip("/") + "/"]
        if dry_run:
            print(" ".join(shlex.quote(c) for c in cmd))
            return cmd
        run(cmd, check=True)
    print(f"Uploaded to {dest}. Serve that folder over HTTPS, for example with Caddy:\n"
          f"    finux.tech {{\n        root * /var/www/finux\n        file_server\n    }}")
    if signer:
        print(f"Signed with:\n    {signer}\n"
              "Publish that line somewhere else too (the Finux README), so people can check it against a copy "
              "the server didn't give them.")
    return cmd


def main(argv=None):
    ap = argparse.ArgumentParser(prog="finux-share", description="Share a Finux image: home network first, then the internet.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lan = sub.add_parser("lan", help="serve the images to your home network only")
    lan.add_argument("images", nargs="*", help="image files or folders (default: this folder)")
    lan.add_argument("--port", type=int, default=PORT, help=f"port to serve on (default {PORT})")
    lan.add_argument("--bind", help="address to listen on (default: this computer's home-network address)")
    wan = sub.add_parser("wan", help="upload the images, page and checksums to a web server")
    wan.add_argument("dest", help="where to copy them: an rsync destination such as you@finux.tech:/var/www/finux")
    wan.add_argument("images", nargs="*", help="image files or folders (default: this folder)")
    wan.add_argument("--sign", metavar="KEY", help="sign SHA256SUMS with this SSH private key, e.g. ~/.ssh/id_ed25519")
    wan.add_argument("--dry-run", action="store_true", help="print the rsync command instead of running it")
    a = ap.parse_args(argv)
    try:
        images = find_images(a.images)
        sums = checksums(images)
        if a.cmd == "lan":
            serve_lan(images, sums, a.port, a.bind)
        else:
            publish_wan(images, sums, a.dest, a.sign, a.dry_run)
    except ShareError as e:
        sys.exit(str(e))
    except subprocess.CalledProcessError as e:
        sys.exit(f"{Path(e.cmd[0]).name} stopped with exit code {e.returncode}")


if __name__ == "__main__":
    main()
