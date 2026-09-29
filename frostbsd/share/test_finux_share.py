"""Tests for finux-share (finux_share.py).

    cd frostbsd/share && python3 -m unittest test_finux_share -v

Standard library only. The upload and signing tests run real rsync and ssh-keygen
when they're installed, and are skipped when they aren't.
"""
import hashlib
import http.client
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finux_share as fs    # noqa: E402

DATA = bytes(range(256)) * 4096        # a 1 MB stand-in for an image


class ImagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, data=DATA):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_finds_images_in_a_folder(self):
        for name in ("FROSTFORPRESIDENT.img", "FrostOS.x86_64-0.1.iso", "b.img.xz", "notes.txt", "a.qcow2.zst"):
            self.make(name)
        (self.dir / "sub").mkdir()
        self.make("sub/hidden.img")
        self.assertEqual([p.name for p in fs.find_images([str(self.dir)])],
                         ["FROSTFORPRESIDENT.img", "FrostOS.x86_64-0.1.iso", "a.qcow2.zst", "b.img.xz"])

    def test_a_named_file_is_shared_whatever_it_is_called(self):
        p = self.make("custom.bin")
        self.assertEqual(fs.find_images([str(p)]), [p])

    def test_nothing_to_share(self):
        with self.assertRaisesRegex(fs.ShareError, "No Finux image"):
            fs.find_images([str(self.dir)])
        with self.assertRaisesRegex(fs.ShareError, "No such file"):
            fs.find_images([str(self.dir / "missing.img")])
        (self.dir / "x").mkdir()
        a, b = self.make("same.img"), self.make("x/same.img")
        with self.assertRaisesRegex(fs.ShareError, "same name: same.img"):
            fs.find_images([str(a), str(b)])

    def test_checksums_page_and_sums_file(self):
        p = self.make("FROST <1>.img")
        sums = fs.checksums([p], say=lambda *_: None)
        digest = hashlib.sha256(DATA).hexdigest()
        self.assertEqual(sums, {"FROST <1>.img": digest})
        self.assertEqual(fs.sums_text(sums), f"{digest}  FROST <1>.img\n")
        html = fs.page([p], sums)
        self.assertIn("FROST &lt;1&gt;.img</a>", html)           # names are escaped
        self.assertIn('href="FROST%20%3C1%3E.img"', html)
        self.assertIn(digest, html)
        self.assertIn("1.0 MB", html)
        self.assertNotIn("SHA256SUMS.sig", html)
        self.assertIn("ssh-keygen -Y verify", fs.page([p], sums, signer="finux ssh-ed25519 AAAAkey"))


class RangeAndNetworkTest(unittest.TestCase):
    def test_byte_ranges(self):
        br = fs.byte_range
        self.assertEqual(br("bytes=0-99", 1000), (0, 99))
        self.assertEqual(br("bytes=500-", 1000), (500, 999))
        self.assertEqual(br("bytes=-100", 1000), (900, 999))
        self.assertEqual(br("bytes=900-5000", 1000), (900, 999))
        self.assertEqual(br("bytes=-5000", 1000), (0, 999))
        for whole in ("bytes=0-1,5-6", "items=0-5", "bytes=-", "bytes=a-b", "bytes=²-"):
            self.assertIsNone(br(whole, 1000), whole)
        for past in ("bytes=1000-", "bytes=5-2", "bytes=-0"):
            with self.assertRaises(ValueError, msg=past):
                br(past, 1000)

    def test_only_nearby_devices(self):
        for ip in ("192.168.1.20", "10.0.0.7", "172.16.4.4", "127.0.0.1", "::1", "fe80::1%eth0",
                   "fd00::5", "::ffff:192.168.1.9"):
            self.assertTrue(fs.nearby(ip), ip)
        for ip in ("8.8.8.8", "203.0.114.9", "2606:4700::1111", "::ffff:8.8.8.8", "not an ip"):
            self.assertFalse(fs.nearby(ip), ip)


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.img = Path(cls.tmp.name) / "FROSTFORPRESIDENT.img"
        cls.img.write_bytes(DATA)
        fs.Handler.share = fs.Share([cls.img], fs.checksums([cls.img], say=lambda *_: None))
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), fs.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def get(self, path, method="GET", headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request(method, path, headers=headers or {})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r, body

    def test_page_and_sums(self):
        r, body = self.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn(b"FROSTFORPRESIDENT.img", body)
        r, body = self.get("/SHA256SUMS")
        self.assertEqual(body, f"{hashlib.sha256(DATA).hexdigest()}  FROSTFORPRESIDENT.img\n".encode())

    def test_whole_download(self):
        r, body = self.get("/FROSTFORPRESIDENT.img")
        self.assertEqual((r.status, body, r.getheader("Accept-Ranges")), (200, DATA, "bytes"))

    def test_resuming(self):
        r, body = self.get("/FROSTFORPRESIDENT.img", headers={"Range": "bytes=1000-"})
        self.assertEqual((r.status, body), (206, DATA[1000:]))
        self.assertEqual(r.getheader("Content-Range"), f"bytes 1000-{len(DATA) - 1}/{len(DATA)}")
        r, body = self.get("/FROSTFORPRESIDENT.img", headers={"Range": "bytes=-10"})
        self.assertEqual((r.status, body), (206, DATA[-10:]))
        r, body = self.get("/FROSTFORPRESIDENT.img", headers={"Range": f"bytes={len(DATA)}-"})
        self.assertEqual((r.status, r.getheader("Content-Range")), (416, f"bytes */{len(DATA)}"))

    def test_head(self):
        r, body = self.get("/FROSTFORPRESIDENT.img", method="HEAD")
        self.assertEqual((r.status, body, r.getheader("Content-Length")), (200, b"", str(len(DATA))))

    def test_nothing_else_is_served(self):
        for path in ("/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/test_finux_share.py", "/sub/FROSTFORPRESIDENT.img"):
            self.assertEqual(self.get(path)[0].status, 404, path)

    def test_far_away_devices_are_turned_away(self):
        with mock.patch.object(fs, "nearby", return_value=False):
            r, body = self.get("/FROSTFORPRESIDENT.img")
        self.assertEqual(r.status, 403)
        self.assertIn(b"home network only", body)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.img = self.dir / "FROSTFORPRESIDENT.img"
        self.img.write_bytes(DATA)
        self.sums = fs.checksums([self.img], say=lambda *_: None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_lists_what_goes_up(self):
        with mock.patch("builtins.print"):
            cmd = fs.publish_wan([self.img], self.sums, "me@finux.tech:/var/www/finux", key="~/.ssh/id_ed25519",
                                 dry_run=True)
        self.assertEqual(cmd[-1], "me@finux.tech:/var/www/finux/")
        self.assertIn("--partial", cmd)
        self.assertEqual([Path(c).name for c in cmd[-5:-1]],
                         ["index.html", "SHA256SUMS", "SHA256SUMS.sig", "FROSTFORPRESIDENT.img"])

    @unittest.skipUnless(shutil.which("rsync"), "rsync isn't installed")
    def test_upload_to_a_folder(self):
        dest = self.dir / "www"
        with mock.patch("builtins.print"):
            fs.publish_wan([self.img], self.sums, str(dest), run=lambda cmd, check: subprocess.run(
                cmd, check=check, stdout=subprocess.DEVNULL))
        self.assertEqual(sorted(p.name for p in dest.iterdir()), ["FROSTFORPRESIDENT.img", "SHA256SUMS", "index.html"])
        self.assertEqual((dest / "FROSTFORPRESIDENT.img").read_bytes(), DATA)
        self.assertEqual((dest / "SHA256SUMS").read_text(), fs.sums_text(self.sums))

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen isn't installed")
    def test_signed_sums_verify(self):
        key = self.dir / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        sums = self.dir / "SHA256SUMS"
        sums.write_text(fs.sums_text(self.sums))
        signer = fs.sign(sums, str(key))
        self.assertTrue(signer.startswith("finux ssh-ed25519 "))
        (self.dir / "allowed_signers").write_text(signer + "\n")
        with open(sums, "rb") as f:
            ok = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(self.dir / "allowed_signers"), "-I", "finux",
                                 "-n", "finux", "-s", str(sums) + ".sig"], stdin=f, capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)


if __name__ == "__main__":
    unittest.main()
