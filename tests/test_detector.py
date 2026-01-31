from __future__ import annotations

import threading
from collections import namedtuple
from unittest.mock import patch

from dirsync.detector import DriveDetector

FakePart = namedtuple("FakePart", ["device", "mountpoint", "fstype", "opts", "maxfile", "maxpath"])


def _fake_part(mountpoint, fstype="ext4"):
    return FakePart(
        device="/dev/sda1",
        mountpoint=mountpoint,
        fstype=fstype,
        opts="rw",
        maxfile=255,
        maxpath=1024,
    )


class TestPseudoMountFiltering:
    def test_skips_tmpfs(self):
        new_calls = []
        known_calls = []
        detector = DriveDetector(new_calls.append, known_calls.append)
        part = _fake_part("/run/user/1000", fstype="tmpfs")
        assert detector._is_pseudo_mount(part) is True

    def test_skips_proc(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/proc", fstype="proc")
        assert detector._is_pseudo_mount(part) is True

    def test_skips_sysfs(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/sys", fstype="sysfs")
        assert detector._is_pseudo_mount(part) is True

    def test_skips_snap_prefix(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/snap/core20/1974", fstype="squashfs")
        assert detector._is_pseudo_mount(part) is True

    def test_skips_boot(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/boot", fstype="ext4")
        assert detector._is_pseudo_mount(part) is True

    def test_allows_real_mount(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/mnt/usb", fstype="ext4")
        assert detector._is_pseudo_mount(part) is False

    def test_allows_fuseblk(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/mnt/ntfs", fstype="fuseblk")
        assert detector._is_pseudo_mount(part) is False

    def test_skips_unknown_fuse(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/mnt/something", fstype="fuse.gvfsd-fuse")
        assert detector._is_pseudo_mount(part) is True

    def test_skips_doc_portal(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        part = _fake_part("/run/user/1000/doc", fstype="fuse.portal")
        assert detector._is_pseudo_mount(part) is True


class TestTargetDetection:
    def test_target_on_mount(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        assert detector._is_target_on_mount("/mnt/usb/backups", "/mnt/usb") is True

    def test_target_not_on_mount(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        assert detector._is_target_on_mount("/mnt/usb/backups", "/mnt/other") is False

    def test_target_equals_mount(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        assert detector._is_target_on_mount("/mnt/usb", "/mnt/usb") is True

    def test_has_registered_target_on_mount(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        detector.watch_targets({"/mnt/usb/backup", "/data/archive"})
        assert detector._has_registered_target_on_mount("/mnt/usb") is True
        assert detector._has_registered_target_on_mount("/data") is True
        assert detector._has_registered_target_on_mount("/mnt/other") is False


class TestWatchTargets:
    def test_updates_registered_targets(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        detector.watch_targets({"/a", "/b"})
        assert len(detector.registered_targets) == 2
        detector.watch_targets({"/c"})
        assert len(detector.registered_targets) == 1


class TestCurrentMounts:
    def test_filters_pseudo_mounts(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        fake_partitions = [
            _fake_part("/", "ext4"),
            _fake_part("/mnt/usb", "ext4"),
            _fake_part("/proc", "proc"),
            _fake_part("/sys", "sysfs"),
            _fake_part("/run/user/1000", "tmpfs"),
        ]
        with patch("psutil.disk_partitions", return_value=fake_partitions):
            mounts = detector._current_mounts()
        assert any("/mnt/usb" in m for m in mounts)
        assert not any("/proc" in m for m in mounts)
        assert not any("/sys" in m for m in mounts)


class TestDetectorStartStop:
    def test_start_and_stop(self):
        detector = DriveDetector(lambda m: None, lambda m: None)
        # Patch sleep to return immediately so the thread loop checks _stop quickly
        with patch("time.sleep", return_value=None):
            detector.start()
            assert detector._thread is not None
            assert detector._thread.is_alive()
            detector.stop()
            detector._thread.join(timeout=2)
            assert not detector._thread.is_alive()

    def test_detects_new_mount(self):
        new_mounts_seen = []
        new_event = threading.Event()

        def on_new(mount):
            new_mounts_seen.append(mount)
            new_event.set()

        detector = DriveDetector(on_new, lambda m: None)
        detector.known = set()

        fake_partitions = [_fake_part("/mnt/usb", "ext4")]
        with patch("psutil.disk_partitions", return_value=fake_partitions):
            with patch("time.sleep", side_effect=lambda _: detector._stop.set()):
                detector._run()

        assert len(new_mounts_seen) > 0
