"""Current detector recorder contracts, using SYNTHETIC streams and a saved corpus.

Every wire stream constructed here is SYNTHETIC. The marker-delimited payload is
a transport fixture, not a decoded camera image. The retained night session is
read directly as events, sidecars and JPEGs; no original serial stream or learned
background is reconstructed. Tests require no board, network, compiler or model.
"""
import base64
import contextlib
import hashlib
from html.parser import HTMLParser
import io
import itertools
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import record_photos
from record_photos import Receiver, fnv1a, save_photo
from recording import SCHEMA_VERSION, analyze_session, summary_from_analysis, validate_frame


SYNTHETIC_JPEG = b"\xff\xd8SYNTHETIC-TRANSPORT-FIXTURE\xff\xd9"
NIGHT_SESSION = (Path(__file__).resolve().parents[1] / "tests" / "captures" /
                 "20261123-002523-561342-outside-dark-inspection")


def synthetic_line(message):
    return (message + "\n").encode("utf-8")


def synthetic_metadata(number, pixels=0, state="CLEAR", cutoff=7.0):
    return {
        "frame": number, "state": state,
        "area_percent": round(pixels * 100 / 4800, 3),
        "cutoff_percent": cutoff, "changed_pixels": pixels,
        "brightness_shift": 0,
        "bbox": [10, 10, 40, 40] if pixels else [0, 0, 0, 0],
        "grid": [80, 60], "pir": 1, "baseline_samples": 12,
        "jpeg_bytes": len(SYNTHETIC_JPEG), "fnv1a": fnv1a(SYNTHETIC_JPEG),
    }


def synthetic_scores(number, gray_pixels=0, assisted_pixels=0, enabled=1, extra=""):
    return synthetic_line(
        f"DETECTION_SCORES frame={number} "
        f"grayscale_percent={gray_pixels * 100 / 4800:.3f} "
        f"assisted_percent={assisted_pixels * 100 / 4800:.3f} "
        f"color_enabled={enabled} grayscale_cutoff=7 color_cutoff=10" + extra)


def synthetic_photo(metadata, payload=SYNTHETIC_JPEG, ending=None):
    return (synthetic_line("PHOTO_BEGIN " + json.dumps(metadata)) +
            synthetic_line("PHOTO_DATA " + base64.b64encode(payload).decode("ascii")) +
            synthetic_line("PHOTO_END " + str(metadata["frame"] if ending is None else ending)))


def synthetic_frame(number, pixels=0, state="CLEAR", cutoff=7.0, *,
                    gray_pixels=None, assisted_pixels=None, enabled=1,
                    photo=False, scores=True):
    metadata = synthetic_metadata(number, pixels, state, cutoff)
    prefix = synthetic_scores(
        number, pixels if gray_pixels is None else gray_pixels,
        pixels if assisted_pixels is None else assisted_pixels, enabled) if scores else b""
    return (prefix + synthetic_line("MOTION " + json.dumps(metadata)) +
            (synthetic_photo(metadata) if photo else b""))


def file_identity(path):
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest(), path.stat().st_mtime_ns


def synthetic_huge_metadata_cases():
    for field in ("area_percent", "cutoff_percent"):
        for sign in (1, -1):
            metadata = synthetic_metadata(1)
            metadata[field] = sign * 10 ** 400
            yield field, sign, metadata


def synthetic_invalid_photo_geometry():
    """Malformed optional geometry, independent of valid photo transport."""
    cases = [
        ("huge_x", {"bbox": [10 ** 400, 0, 1, 1], "grid": [80, 60]}),
        ("huge_width", {"bbox": [0, 0, 10 ** 400, 1], "grid": [80, 60]}),
        ("negative_origin", {"bbox": [-1, 0, 1, 1], "grid": [80, 60]}),
        ("negative_extent", {"bbox": [0, 0, -1, 1], "grid": [80, 60]}),
        ("outside_right_edge", {"bbox": [79, 0, 2, 1], "grid": [80, 60]}),
        ("outside_bottom_edge", {"bbox": [0, 59, 1, 2], "grid": [80, 60]}),
        ("zero_grid", {"bbox": [0, 0, 1, 1], "grid": [0, 60]}),
        ("negative_grid", {"bbox": [0, 0, 1, 1], "grid": [80, -60]}),
        ("boolean_coordinate", {"bbox": [True, 0, 1, 1], "grid": [80, 60]}),
        ("boolean_grid", {"bbox": [0, 0, 1, 1], "grid": [True, 60]}),
        ("text_coordinate", {"bbox": ["0", 0, 1, 1], "grid": [80, 60]}),
        ("short_box", {"bbox": [0, 0, 1], "grid": [80, 60]}),
        ("short_grid", {"bbox": [0, 0, 1, 1], "grid": [80]}),
        ("box_without_grid", {"bbox": [0, 0, 1, 1]}),
        ("grid_without_box", {"grid": [80, 60]}),
        ("null_geometry", {"bbox": None, "grid": None}),
    ]
    yield from cases


def event_rows(session):
    return [json.loads(line) for line in (session / "events.jsonl").read_text().splitlines()]


def write_synthetic_event_rows(session, rows):
    (session / "events.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class SyntheticCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="SYNTHETIC-detector-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.session_number = 0

    def new_session(self):
        self.session_number += 1
        session = self.root / f"SYNTHETIC-{self.session_number:03d}"
        session.mkdir()
        return session

    def record(self, raw, *, chunk_size=None, reason="duration_limit"):
        session = self.new_session()
        receiver = Receiver(session, "SYNTHETIC")
        self.addCleanup(receiver.finish)
        if chunk_size is None:
            receiver.feed(raw)
        else:
            for offset in range(0, len(raw), chunk_size):
                receiver.feed(raw[offset:offset + chunk_size])
        receiver.finish(reason)
        return session, receiver, analyze_session(session)


class TransportTests(SyntheticCase):
    def test_first_line_fragmented_utf8_and_exact_raw_spans(self):
        raw = (synthetic_line("STATUS note=SYNTHETIC-café-雪") +
               synthetic_frame(7, photo=True) + b"unfinished-SYNTHETIC")
        session, receiver, result = self.record(raw, chunk_size=1)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        self.assertEqual(result["counts"]["motion_frame_records"], 1)
        self.assertEqual(result["counts"]["verified_photos"], 1)
        self.assertEqual(next(session.glob("*.jpg")).read_bytes(), SYNTHETIC_JPEG)
        rows = [json.loads(line) for line in (session / "events.jsonl").read_text().splitlines()]
        self.assertEqual(rows[0]["device_message"], "STATUS note=SYNTHETIC-café-雪")
        self.assertTrue(any(row.get("recorder_event") == "TRAILING_FRAGMENT" for row in rows))
        sequences = [row["_host"]["sequence"] for row in rows]
        self.assertEqual(sequences, list(range(1, len(rows) + 1)))
        spans = [(row["_host"]["raw_start"], row["_host"]["raw_end"]) for row in rows
                 if row["_host"]["raw_start"] is not None]
        self.assertTrue(all(0 <= start < end <= len(raw) for start, end in spans))
        self.assertEqual(raw[slice(*spans[0])], synthetic_line("STATUS note=SYNTHETIC-café-雪"))
        before = file_identity(session / "events.jsonl")
        receiver.finish()
        self.assertEqual(file_identity(session / "events.jsonl"), before)

    def test_corrupt_photo_variants_keep_raw_without_successful_pair(self):
        metadata = synthetic_metadata(1)
        variants = {
            "wrong_end": synthetic_photo(metadata, ending=2),
            "wrong_checksum": synthetic_photo(dict(metadata, fnv1a="00000000")),
            "wrong_length": synthetic_photo(dict(metadata, jpeg_bytes=len(SYNTHETIC_JPEG) + 1)),
            "bad_base64": (synthetic_line("PHOTO_BEGIN " + json.dumps(metadata)) +
                           b"PHOTO_DATA !invalid!\nPHOTO_END 1\n"),
            "missing_markers": synthetic_photo(
                dict(metadata, jpeg_bytes=4, fnv1a=fnv1a(b"nope")), b"nope"),
            "oversized_declaration": synthetic_line(
                "PHOTO_BEGIN " + json.dumps(dict(metadata, jpeg_bytes=500001))),
            "oversized_encoded": (synthetic_line("PHOTO_BEGIN " + json.dumps(metadata)) +
                                  b"PHOTO_DATA " + b"A" * 700001 + b"\nPHOTO_END 1\n"),
        }
        for name, raw in variants.items():
            with self.subTest(name=name):
                session, _, result = self.record(raw)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                self.assertEqual(list(session.glob("*.jpg")), [])
                self.assertEqual(result["counts"]["verified_photos"], 0)
                self.assertTrue(result["errors"])

    def test_interrupted_photo_and_replacement_header_are_explicit(self):
        metadata = synthetic_metadata(1)
        prefix = synthetic_line("PHOTO_BEGIN " + json.dumps(metadata)) + b"PHOTO_DATA /9g=\n"
        for raw in (prefix, prefix + synthetic_photo(synthetic_metadata(2))):
            with self.subTest(replacement=b"PHOTO_END 2" in raw):
                session, _, result = self.record(raw)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                self.assertTrue(result["errors"])
                self.assertEqual(result["counts"]["verified_photos"], int(b"PHOTO_END 2" in raw))

    def test_duplicate_frame_ids_never_overwrite_with_or_without_boot(self):
        for separator in (b"", b"BOOT SYNTHETIC-reset\n"):
            with self.subTest(boot=bool(separator)):
                raw = synthetic_frame(7, photo=True) + separator + synthetic_frame(7, photo=True)
                session, _, result = self.record(raw)
                images = list(session.glob("*.jpg"))
                self.assertEqual(len(images), 2)
                self.assertEqual(len({path.name for path in images}), 2)
                self.assertTrue(all(path.read_bytes() == SYNTHETIC_JPEG for path in images))
                self.assertEqual(result["counts"]["photos_saved"], 2)

    def test_oversized_unterminated_line_discards_suffix_until_newline(self):
        session = self.new_session()
        receiver = Receiver(session, "SYNTHETIC-oversized")
        self.addCleanup(receiver.finish)
        oversized = b"S" * 800001
        suffix = synthetic_line("MOTION " + json.dumps(synthetic_metadata(1)))
        valid = synthetic_frame(2)
        receiver.feed(oversized)
        receiver.feed(suffix)
        receiver.feed(valid)
        receiver.finish()
        result = analyze_session(session)
        self.assertEqual((session / "serial.raw").read_bytes(), oversized + suffix + valid)
        self.assertEqual([frame["metadata"]["frame"] for frame in result["frames"]], [2])
        self.assertTrue(result["errors"])

    def test_invalid_utf8_json_and_duplicate_keys_remain_in_raw(self):
        duplicate = json.dumps(synthetic_metadata(1)).replace('"frame": 1', '"frame": 1, "frame": 2')
        raw = b"\xff\xfe\nMOTION {broken}\n" + synthetic_line("MOTION " + duplicate)
        session, _, result = self.record(raw)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        self.assertEqual(result["counts"]["motion_frame_records"], 0)
        self.assertTrue(result["errors"])

    def test_filename_state_cannot_escape_output(self):
        metadata = synthetic_metadata(1)
        metadata["state"] = "../../outside"
        with self.assertRaises((ValueError, TypeError)):
            save_photo(self.root, metadata, [base64.b64encode(SYNTHETIC_JPEG).decode()], "1")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_selected_region_metadata_is_an_integrity_error(self):
        valid = synthetic_metadata(1, 336, "CONFIRMING")
        invalid = [dict(valid, area_percent=55), dict(valid, frame=True),
                   dict(valid, bbox=[70, 10, 40, 40]), dict(valid, changed_pixels=-1)]
        for metadata in invalid:
            with self.subTest(metadata=metadata):
                raw = synthetic_line("MOTION " + json.dumps(metadata))
                session, _, result = self.record(raw)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                self.assertTrue(result["errors"])
                self.assertEqual(result["counts"]["detector_frame_records"], 0)

    def test_damaged_saved_event_utf8_is_reported_without_rewriting_input(self):
        session = self.new_session()
        path = session / "events.jsonl"
        path.write_bytes(b'{"device_message":"SYNTHETIC retained event"}\n\xff\xfe\n' +
                         synthetic_line(json.dumps(synthetic_metadata(1))))
        before = file_identity(path)
        result = analyze_session(session)
        self.assertTrue(result["errors"])
        self.assertEqual([row["metadata"]["frame"] for row in result["frames"]], [1])
        self.assertEqual(file_identity(path), before)

    def test_huge_signed_area_and_cutoff_are_value_errors(self):
        for field, sign, metadata in synthetic_huge_metadata_cases():
            with self.subTest(field=field, sign=sign):
                with self.assertRaises(ValueError):
                    validate_frame(metadata, detector=True)

    def test_huge_numeric_row_does_not_drop_later_transfer_in_same_feed(self):
        for field, sign, metadata in synthetic_huge_metadata_cases():
            with self.subTest(field=field, sign=sign):
                raw = (synthetic_line("MOTION " + json.dumps(metadata)) +
                       synthetic_frame(2, photo=True))
                session, _, result = self.record(raw)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                self.assertEqual([row["metadata"]["frame"] for row in result["frames"]], [2])
                self.assertEqual(result["counts"]["verified_photos"], 1)
                self.assertTrue(result["errors"])

    def test_saved_events_keep_good_rows_after_huge_numeric_metadata(self):
        for field, sign, metadata in synthetic_huge_metadata_cases():
            with self.subTest(field=field, sign=sign):
                session = self.new_session()
                path = session / "events.jsonl"
                write_synthetic_event_rows(session, [metadata, synthetic_metadata(2)])
                before = file_identity(path)
                result = analyze_session(session)
                self.assertTrue(result["errors"])
                self.assertEqual([row["metadata"]["frame"] for row in result["frames"]], [2])
                self.assertEqual(file_identity(path), before)


class PhotoGeometryTests(SyntheticCase):
    """Optional PHOTO geometry cannot discard sound bytes or break a gallery."""
    def photo_only(self, number, **geometry):
        return {"frame": number, "state": "CAMERA_TEST",
                "jpeg_bytes": len(SYNTHETIC_JPEG), "fnv1a": fnv1a(SYNTHETIC_JPEG),
                **geometry}

    def test_malformed_geometry_retains_photos_and_reports_unavailable_overlay(self):
        for name, geometry in synthetic_invalid_photo_geometry():
            with self.subTest(case=name):
                metadata = self.photo_only(1, **geometry)
                raw = (synthetic_photo(metadata) +
                       synthetic_photo(self.photo_only(2, bbox=[20, 15, 40, 30], grid=[80, 60])))
                session, _, analysis = self.record(raw)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                self.assertEqual(analysis["counts"]["verified_photos"], 2)
                self.assertEqual(analysis["frames"], [])
                first = next(photo for photo in analysis["photos"] if photo["frame"] == 1)
                self.assertEqual({key: first["metadata"][key] for key in geometry}, geometry)
                self.assertEqual(first["geometry"]["status"], "invalid")
                self.assertTrue(any(problem["code"] == "invalid_photo_geometry" for problem in analysis["errors"]))
                self.assertTrue(all(photo["matching_event_lines"] == [] for photo in analysis["photos"]))
                self.assertTrue(all(path.read_bytes() == SYNTHETIC_JPEG for path in session.glob("*.jpg")))
                record_photos.write_gallery(session, analysis)
                page = (session / "index.html").read_text()
                references = ImageReferences()
                references.feed(page)
                self.assertEqual(len(references.sources), 2)
                self.assertEqual(len(references.boxes), 1)
                self.assertIn("geometry is invalid", page)
                self.assertIn("no box is drawn", page)

    def test_optional_empty_and_bounded_geometry_do_not_invent_measurements(self):
        cases = [
            ("not_reported", {}, None),
            ("empty", {"bbox": [0, 0, 0, 0], "grid": [80, 60]}, None),
            ("valid", {"bbox": [20, 15, 40, 30], "grid": [80, 60]}, [25, 25, 50, 50]),
            ("valid", {"bbox": [0.25, 0.5, 0.5, 1.0], "grid": [1, 2]}, [25, 25, 50, 50]),
            ("valid", {"bbox": [10 ** 400, 0.0, 10 ** 400, 1.0],
                       "grid": [4 * 10 ** 400, 2.0]}, [25, 0, 25, 50]),
        ]
        for expected, geometry, percentages in cases:
            with self.subTest(expected=expected, geometry=geometry):
                session, _, analysis = self.record(synthetic_photo(self.photo_only(1, **geometry)))
                self.assertFalse(analysis["errors"])
                self.assertEqual(analysis["counts"]["verified_photos"], 1)
                self.assertEqual(analysis["counts"]["motion_frame_records"], 0)
                self.assertEqual(analysis["photos"][0]["geometry"]["status"], expected)
                record_photos.write_gallery(session, analysis)
                references = ImageReferences()
                references.feed((session / "index.html").read_text())
                self.assertEqual(len(references.boxes), int(percentages is not None))
                if percentages is not None:
                    properties = dict(entry.split(":", 1) for entry in references.boxes[0].split(";") if entry)
                    actual = {name: float(value.removesuffix("%")) for name, value in properties.items()}
                    self.assertEqual(actual, dict(zip(("left", "top", "width", "height"), percentages)))

    def test_saved_invalid_geometry_analysis_preserves_original_artifacts(self):
        session, _, _ = self.record(synthetic_photo(self.photo_only(1)))
        sidecar = next(session.glob("frame*.json"))
        saved = json.loads(sidecar.read_text())
        saved.update(bbox=[10 ** 400, 0, 1, 1], grid=[80, 60])
        sidecar.write_text(json.dumps(saved), encoding="utf-8")
        before = {path.name: file_identity(path) for path in session.iterdir()}
        analysis = analyze_session(session)
        self.assertEqual(analysis["counts"]["verified_photos"], 1)
        self.assertTrue(any(problem["code"] == "invalid_photo_geometry" for problem in analysis["errors"]))
        self.assertEqual({path.name: file_identity(path) for path in session.iterdir()}, before)


class PhotoBindingTests(SyntheticCase):
    """SYNTHETIC new-format bindings must never fall back to legacy guesses."""
    def test_explicit_null_photo_binding_stays_unpaired_across_boot(self):
        metadata = synthetic_metadata(7, 384, "CONFIRMING")
        raw = (synthetic_scores(7, 384, 438) + synthetic_line("MOTION " + json.dumps(metadata)) +
               b"BOOT SYNTHETIC-restart\n" + synthetic_photo(metadata))
        session, _, result = self.record(raw)
        sidecar = json.loads(next(session.glob("frame*.json")).read_text())
        self.assertEqual(sidecar["record_schema"], 3)
        self.assertIsNone(sidecar["motion_event_sequence"])
        self.assertEqual(result["frames"][0]["scores"]["assisted_percent"], 9.125)
        self.assertTrue(result["photos"][0]["checksum_verified"])
        self.assertEqual(result["photos"][0]["matching_event_lines"], [])
        self.assertTrue(result["warnings"])
        self.assertFalse(result["errors"])

    def test_missing_or_invalid_new_binding_never_uses_legacy_matching(self):
        variants = ("missing", "boolean", "string", "zero", "negative", "unknown",
                    "host_marker_only", "stripped_markers", "manifest_only")
        for variant in variants:
            with self.subTest(variant=variant):
                session, _, _ = self.record(synthetic_frame(7, photo=True))
                path = next(session.glob("frame*.json"))
                metadata = json.loads(path.read_text())
                if variant in ("missing", "host_marker_only", "stripped_markers", "manifest_only"):
                    del metadata["motion_event_sequence"]
                    if variant in ("host_marker_only", "stripped_markers", "manifest_only"):
                        del metadata["record_schema"]
                        metadata.pop("_host", None)
                    if variant == "host_marker_only":
                        metadata["_host"] = {}
                else:
                    metadata["motion_event_sequence"] = {
                        "boolean": True, "string": "2", "zero": 0,
                        "negative": -1, "unknown": 999999,
                    }[variant]
                path.write_text(json.dumps(metadata), encoding="utf-8")
                if variant == "manifest_only":
                    write_synthetic_event_rows(session, [synthetic_metadata(7)])
                    (session / "run_manifest.json").write_text(
                        json.dumps({"schema_version": 3, "closed": False, "artifacts": []}),
                        encoding="utf-8")
                result = analyze_session(session)
                self.assertTrue(result["photos"][0]["checksum_verified"])
                self.assertEqual(result["photos"][0]["matching_event_lines"], [])
                self.assertTrue(result["errors"])

    def test_valid_nonnull_binding_matches_canonical_motion_and_photo_receipt(self):
        session, _, result = self.record(synthetic_frame(7, photo=True))
        frame = result["frames"][0]
        metadata_path = next(session.glob("frame*.json"))
        metadata = json.loads(metadata_path.read_text())
        self.assertGreater(metadata["motion_event_sequence"], 0)
        self.assertEqual(metadata["motion_event_sequence"], frame["metadata"]["_host"]["sequence"])
        self.assertEqual(result["photos"][0]["matching_event_lines"], [frame["line"]])
        saved = [row for row in event_rows(session) if row.get("recorder_event") == "PHOTO_SAVED"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["metadata_file"], metadata_path.name)
        self.assertEqual(saved[0]["motion_event_sequence"], metadata["motion_event_sequence"])
        self.assertFalse(result["errors"])

    def test_nonnull_binding_must_match_device_identity_even_if_receipt_agrees(self):
        first = synthetic_metadata(7)
        raw = (synthetic_frame(7) + synthetic_frame(8) + synthetic_photo(first))
        session, _, original = self.record(raw)
        wrong_sequence = original["frames"][1]["metadata"]["_host"]["sequence"]
        metadata_path = next(session.glob("frame*.json"))
        metadata = json.loads(metadata_path.read_text())
        metadata["motion_event_sequence"] = wrong_sequence
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        rows = event_rows(session)
        for row in rows:
            if row.get("recorder_event") == "PHOTO_SAVED":
                row["motion_event_sequence"] = wrong_sequence
        write_synthetic_event_rows(session, rows)
        result = analyze_session(session)
        self.assertTrue(result["photos"][0]["checksum_verified"])
        self.assertEqual(result["photos"][0]["matching_event_lines"], [])
        self.assertTrue(result["errors"])

    def test_nonnull_binding_cannot_cross_boot_even_with_identical_device_metadata(self):
        metadata = synthetic_metadata(7)
        raw = synthetic_frame(7) + b"BOOT SYNTHETIC-restart\n" + synthetic_photo(metadata)
        session, _, original = self.record(raw)
        old_sequence = original["frames"][0]["metadata"]["_host"]["sequence"]
        path = next(session.glob("frame*.json"))
        sidecar = json.loads(path.read_text())
        sidecar["motion_event_sequence"] = old_sequence
        path.write_text(json.dumps(sidecar), encoding="utf-8")
        rows = event_rows(session)
        for row in rows:
            if row.get("recorder_event") == "PHOTO_SAVED":
                row["motion_event_sequence"] = old_sequence
        write_synthetic_event_rows(session, rows)
        result = analyze_session(session)
        self.assertTrue(result["photos"][0]["checksum_verified"])
        self.assertEqual(result["photos"][0]["matching_event_lines"], [])
        self.assertTrue(result["errors"])

    def test_nonnull_binding_requires_matching_saved_photo_receipt(self):
        for variant in ("missing_receipt", "conflicting_receipt"):
            with self.subTest(variant=variant):
                session, _, _ = self.record(synthetic_frame(7, photo=True))
                rows = event_rows(session)
                if variant == "missing_receipt":
                    rows = [row for row in rows if row.get("recorder_event") != "PHOTO_SAVED"]
                else:
                    for row in rows:
                        if row.get("recorder_event") == "PHOTO_SAVED":
                            row["motion_event_sequence"] = None
                write_synthetic_event_rows(session, rows)
                result = analyze_session(session)
                self.assertTrue(result["photos"][0]["checksum_verified"])
                self.assertEqual(result["photos"][0]["matching_event_lines"], [])
                self.assertTrue(result["errors"])

    def test_nonnull_binding_rejects_ambiguous_or_later_canonical_motion(self):
        for variant in ("ambiguous_motion", "motion_after_photo"):
            with self.subTest(variant=variant):
                if variant == "ambiguous_motion":
                    session, _, _ = self.record(synthetic_frame(7, photo=True))
                    rows = event_rows(session)
                    index = next(i for i, row in enumerate(rows)
                                 if row.get("frame") == 7 and "recorder_event" not in row)
                    rows.insert(index + 1, json.loads(json.dumps(rows[index])))
                else:
                    session, _, _ = self.record(synthetic_photo(synthetic_metadata(7)) + synthetic_frame(7))
                    rows = event_rows(session)
                    motion = next(row for row in rows if row.get("frame") == 7
                                  and "recorder_event" not in row)
                    future_sequence = motion["_host"]["sequence"]
                    path = next(session.glob("frame*.json"))
                    metadata = json.loads(path.read_text())
                    metadata["motion_event_sequence"] = future_sequence
                    path.write_text(json.dumps(metadata), encoding="utf-8")
                    for row in rows:
                        if row.get("recorder_event") == "PHOTO_SAVED":
                            row["motion_event_sequence"] = future_sequence
                write_synthetic_event_rows(session, rows)
                result = analyze_session(session)
                self.assertTrue(result["photos"][0]["checksum_verified"])
                self.assertEqual(result["photos"][0]["matching_event_lines"], [])
                self.assertTrue(result["errors"])


class CurrentProtocolTests(SyntheticCase):
    def test_wait_timeout_and_unresolved_wait_are_not_camera_bursts(self):
        raw = (b"PIR_TRIGGER waiting_for_vibration_s=10 camera=STANDBY\n"
               b"STATUS state=WAIT_FOR_VIBRATION\nVIBRATION_TIMEOUT camera=STANDBY\n"
               b"PIR_TRIGGER waiting_for_vibration_s=10 camera=STANDBY\n")
        _, _, result = self.record(raw)
        self.assertEqual([wait["outcome"] for wait in result["waits"]], ["timed_out", "unresolved"])
        self.assertEqual(result["camera_bursts"], [])
        self.assertEqual(result["counts"]["pir_wait_openings"], 2)
        self.assertEqual(result["counts"]["unresolved_waits"], 1)

    def test_vibration_start_observed_without_prior_pir(self):
        raw = (b"VIBRATION_RECEIVED starting_max_10_frames=1\n" + synthetic_frame(1) +
               b"BURST_END frames=1 large_confirmed=0\n")
        _, _, result = self.record(raw)
        burst = result["camera_bursts"][0]
        self.assertTrue(burst["start_observed"])
        self.assertTrue(burst["boundary_complete"])
        self.assertIsNone(burst["preceding_wait"])
        self.assertEqual(result["counts"]["fully_observed_wait_to_capture_sequences"], 0)

    def test_bench_message_variants_do_not_start_camera_bursts(self):
        raw = (b"VIBRATION_RECEIVED alarm_busy=0\nPIR_TRIGGER count=1 elapsed_ms=200\n"
               b"VIBRATION_TIMEOUT camera=STANDBY\n")
        _, _, result = self.record(raw)
        self.assertEqual(result["camera_bursts"], [])
        self.assertEqual(result["counts"]["pir_wait_openings"], 0)
        self.assertEqual(result["counts"]["motion_frame_records"], 0)

    def test_explicit_start_variants_and_missing_end_remain_distinct(self):
        cases = [
            (b"PIR_TRIGGER test=PIR_WIFI_CAMERA starting_max_10_frames=1\n", "pir_test"),
            (b"PIR_TRIGGER starting_max_10_frames=1\n", "pir_direct"),
        ]
        for start, kind in cases:
            with self.subTest(kind=kind):
                _, _, result = self.record(start + synthetic_frame(1))
                burst = result["camera_bursts"][0]
                self.assertEqual(burst["start_kind"], kind)
                self.assertEqual(burst["status"], "unfinished")
                self.assertFalse(burst["boundary_complete"])
                self.assertIsNone(burst["declared_attempts"])

    def test_burst_ending_does_not_invent_missing_capture_start(self):
        _, _, result = self.record(synthetic_frame(7) + b"BURST_END frames=1 large_confirmed=0\n")
        self.assertEqual(len(result["camera_bursts"]), 1)
        burst = result["camera_bursts"][0]
        self.assertFalse(burst["start_observed"])
        self.assertFalse(burst["boundary_complete"])
        self.assertEqual(burst["start_kind"], "unobserved")
        self.assertEqual(result["counts"]["fully_observed_wait_to_capture_sequences"], 0)

    def test_gray_and_assisted_scores_preserve_selected_region(self):
        cases = [
            (384, 432, 1, 384, 7.0),
            (240, 576, 1, 576, 10.0),
            (384, 576, 1, 384, 7.0),
            (240, 432, 1, 240, 7.0),
            (384, 0, 0, 384, 7.0),
            (336, 480, 1, 336, 7.0),
        ]
        for gray, assisted, enabled, selected, cutoff in cases:
            with self.subTest(gray=gray, assisted=assisted, enabled=enabled):
                state = "CONFIRMING" if gray >= 336 or (enabled and assisted >= 480) else "SMALL_CHANGE"
                _, _, result = self.record(synthetic_frame(
                    1, selected, state, cutoff, gray_pixels=gray,
                    assisted_pixels=assisted, enabled=enabled, photo=True))
                frame = result["frames"][0]
                self.assertEqual(frame["score_association"], "matched")
                self.assertEqual(frame["metadata"]["changed_pixels"], selected)
                self.assertEqual(frame["metadata"]["cutoff_percent"], cutoff)
                self.assertEqual(frame["scores"]["grayscale_percent"], round(gray * 100 / 4800, 3))
                self.assertEqual(frame["scores"]["assisted_percent"], round(assisted * 100 / 4800, 3))
                self.assertEqual(result["counts"]["verified_photos"], 1)
                self.assertFalse(result["errors"])

    def test_alternating_routes_preserve_one_burst_and_emitted_states(self):
        gray = dict(pixels=384, gray_pixels=384, assisted_pixels=432, cutoff=7.0)
        assisted = dict(pixels=576, gray_pixels=240, assisted_pixels=576, cutoff=10.0)
        sequences = [
            [(gray, "CONFIRMING"), (assisted, "LARGE_CHANGE")],
            [(assisted, "CONFIRMING"), (gray, "LARGE_CHANGE")],
            [(gray, "CONFIRMING"), (dict(pixels=48), "SMALL_CHANGE"),
             (assisted, "CONFIRMING"), (gray, "LARGE_CHANGE")],
        ]
        for sequence in sequences:
            with self.subTest(states=[state for _, state in sequence]):
                raw = b"VIBRATION_RECEIVED starting_max_10_frames=1\n"
                for number, (values, state) in enumerate(sequence, 1):
                    raw += synthetic_frame(number, state=state, **values)
                raw += synthetic_line(f"BURST_END frames={len(sequence)} large_confirmed=1")
                _, _, result = self.record(raw)
                self.assertEqual(len(result["camera_bursts"]), 1)
                self.assertEqual(result["camera_bursts"][0]["observed_motion_records"], len(sequence))
                self.assertEqual([row["metadata"]["state"] for row in result["frames"]],
                                 [state for _, state in sequence])
                self.assertFalse(result["errors"])

    def test_auxiliary_problems_do_not_discard_valid_photo(self):
        cases = [
            b"",
            synthetic_scores(2),
            synthetic_scores(1) + synthetic_scores(1, gray_pixels=48),
            b"DETECTION_SCORES frame=1 grayscale_percent=NaN assisted_percent=0 color_enabled=1 grayscale_cutoff=7 color_cutoff=10\n",
        ]
        for auxiliary in cases:
            with self.subTest(auxiliary=auxiliary[:80]):
                _, _, result = self.record(auxiliary + synthetic_frame(1, photo=True, scores=False))
                self.assertEqual(result["counts"]["verified_photos"], 1)
                self.assertNotEqual(result["frames"][0]["score_association"], "matched")
                self.assertTrue(result["errors"] or result["warnings"])

    def test_unknown_score_fields_survive_without_cross_boot_join(self):
        raw = (synthetic_scores(1, extra=" future_note=SYNTHETIC-kept") +
               synthetic_frame(1, scores=False) + synthetic_scores(2) +
               b"BOOT SYNTHETIC-restart\n" + synthetic_frame(2, scores=False))
        session, _, result = self.record(raw)
        self.assertEqual(result["frames"][0]["score_association"], "matched")
        self.assertIn('"future_note": "SYNTHETIC-kept"',
                      json.dumps(result["frames"][0]["scores"], sort_keys=True))
        self.assertEqual(result["frames"][1]["score_association"], "missing")
        self.assertIn("future_note=SYNTHETIC-kept", (session / "events.jsonl").read_text())

    def test_reference_route_mismatch_is_not_transfer_corruption(self):
        raw = synthetic_frame(1, 576, "CONFIRMING", 10.0,
                              gray_pixels=384, assisted_pixels=576, photo=True)
        _, _, result = self.record(raw)
        self.assertEqual(result["counts"]["verified_photos"], 1)
        self.assertEqual(result["frames"][0]["metadata"]["changed_pixels"], 576)
        self.assertTrue(result["reference_warnings"])
        self.assertFalse(result["errors"])

    def test_alarm_can_precede_scores_and_frame_without_cross_boot_binding(self):
        prefix = b"VIBRATION_RECEIVED starting_max_10_frames=1\n"
        raw = (prefix + synthetic_frame(52, 384, "CONFIRMING") +
               b"DETERRENT_ON frame=53 count=1\n" + synthetic_frame(53, 432, "LARGE_CHANGE") +
               b"BURST_END frames=2 large_confirmed=1\n")
        _, _, result = self.record(raw)
        alarm = result["software_alarms"][0]
        frame = next(row for row in result["frames"] if row["metadata"]["frame"] == 53)
        self.assertEqual(alarm["association"], "matched")
        self.assertEqual(alarm["matching_frame_lines"], [frame["line"]])
        self.assertEqual(frame["alarm_start_lines"], [alarm["line"]])
        for tail in (b"", b"BOOT SYNTHETIC-restart\n" + synthetic_frame(53)):
            with self.subTest(boot=bool(tail)):
                _, _, clipped = self.record(b"DETERRENT_ON frame=53 count=1\n" + tail)
                self.assertEqual(clipped["software_alarms"][0]["association"], "missing")
                self.assertEqual(clipped["software_alarms"][0]["matching_frame_lines"], [])
                self.assertEqual(clipped["counts"]["photos_saved"], 0)
                if not tail:
                    self.assertEqual(clipped["frames"], [])

    def test_ambiguous_reused_frame_identity_leaves_alarm_unpaired(self):
        raw = (synthetic_frame(7) + synthetic_frame(7) + b"DETERRENT_ON frame=7 count=1\n")
        _, _, result = self.record(raw)
        self.assertEqual(result["software_alarms"][0]["association"], "ambiguous")
        self.assertTrue(all(not frame["alarm_start_lines"] for frame in result["frames"]))

    def test_decode_error_consumes_attempt_without_ending_burst_or_inventing_frame(self):
        raw = (b"VIBRATION_RECEIVED starting_max_10_frames=1\n" +
               synthetic_frame(1, 384, "CONFIRMING") + b"ERROR jpeg_decode\n" +
               synthetic_frame(3, 384, "CONFIRMING") + synthetic_frame(4, 432, "LARGE_CHANGE") +
               b"BURST_END frames=4 large_confirmed=1\n")
        _, _, result = self.record(raw)
        self.assertEqual([row["metadata"]["frame"] for row in result["frames"]], [1, 3, 4])
        self.assertEqual([row["metadata"]["state"] for row in result["frames"]],
                         ["CONFIRMING", "CONFIRMING", "LARGE_CHANGE"])
        self.assertEqual(len(result["camera_bursts"]), 1)
        burst = result["camera_bursts"][0]
        self.assertTrue(burst["boundary_complete"])
        self.assertEqual(burst["observed_motion_records"], 3)
        self.assertEqual(burst["observed_decode_errors"], 1)
        self.assertEqual(burst["declared_attempts"], 4)
        self.assertEqual(burst["reference_accounting"]["status"], "matched")
        self.assertEqual(result["counts"]["application_error_messages"], 1)

    def test_final_decode_attempt_and_unexplained_count_gap_are_distinct(self):
        prefix = b"VIBRATION_RECEIVED starting_max_10_frames=1\n"
        frames = b"".join(synthetic_frame(number) for number in range(1, 10))
        _, _, accounted = self.record(prefix + frames + b"ERROR jpeg_decode\n"
                                      b"BURST_END frames=10 large_confirmed=0 reason=JPEG_DECODE\n")
        self.assertEqual(accounted["camera_bursts"][0]["reference_accounting"]["status"], "matched")
        _, _, missing = self.record(prefix + frames + b"BURST_END frames=10 large_confirmed=0\n")
        self.assertTrue(missing["camera_bursts"][0]["boundary_complete"])
        self.assertEqual(missing["camera_bursts"][0]["reference_accounting"]["status"], "mismatch")
        self.assertTrue(missing["reference_warnings"])
        self.assertFalse(missing["errors"])

    def test_test_only_motion_counts_as_attempt_without_becoming_alarm(self):
        raw = (b"PIR_TRIGGER test=PIR_WIFI_CAMERA starting_max_10_frames=1\n" +
               synthetic_frame(1, 384, "CONFIRMING") +
               synthetic_frame(2, 432, "LARGE_CHANGE_TEST_ONLY") +
               b"".join(synthetic_frame(number) for number in range(3, 11)) +
               b"BURST_END frames=10 large_confirmed=0\n")
        _, _, result = self.record(raw)
        burst = result["camera_bursts"][0]
        self.assertEqual(burst["observed_motion_records"], 10)
        self.assertEqual(burst["reference_accounting"]["status"], "matched")
        self.assertEqual(result["counts"]["diagnostic_frame_records"], 1)
        self.assertEqual(result["counts"]["alarm_start_messages"], 0)
        self.assertNotIn("LARGE_CHANGE_TEST_ONLY", result["detector_state_counts"])

    def test_setup_and_photo_only_diagnostics_remain_separate(self):
        raw = (synthetic_frame(1, state="SETTLING") + synthetic_frame(2, state="CALIBRATING") +
               synthetic_photo(synthetic_metadata(3, state="CAMERA_TEST")))
        _, _, result = self.record(raw)
        self.assertEqual(result["counts"]["calibration_frame_records"], 2)
        self.assertEqual(result["counts"]["detector_frame_records"], 0)
        self.assertEqual(result["counts"]["verified_photos"], 1)
        self.assertEqual(result["photos"][0]["matching_event_lines"], [])
        self.assertEqual(result["camera_bursts"], [])

    def test_unknown_future_state_is_retained_but_not_scored_as_detector(self):
        _, _, result = self.record(synthetic_frame(1, 48, "SYNTHETIC_FUTURE_STATE", photo=True))
        self.assertEqual(result["counts"]["unknown_frame_records"], 1)
        self.assertEqual(result["counts"]["detector_frame_records"], 0)
        self.assertEqual(result["counts"]["verified_photos"], 1)
        self.assertEqual(result["counts"]["alarm_start_messages"], 0)
        self.assertEqual(result["frames"][0]["metadata"]["state"], "SYNTHETIC_FUTURE_STATE")

    def test_device_acknowledgments_reset_work_but_host_requests_do_not(self):
        for acknowledgment in ("ARMED manual_rearm=1 pir=0", "CALIBRATION clear_view_now; starts_in=3_seconds"):
            with self.subTest(acknowledgment=acknowledgment):
                raw = (b"PIR_TRIGGER waiting_for_vibration_s=10 camera=STANDBY\n" +
                       synthetic_line(acknowledgment) +
                       b"VIBRATION_RECEIVED starting_max_10_frames=1\n" + synthetic_frame(1) +
                       synthetic_line(acknowledgment))
                _, _, result = self.record(raw)
                self.assertEqual(result["waits"][0]["outcome"], "reset")
                self.assertEqual(result["camera_bursts"][0]["status"], "aborted")
        session = self.new_session()
        receiver = Receiver(session, "SYNTHETIC-host-request")
        self.addCleanup(receiver.finish)
        receiver.feed(b"VIBRATION_RECEIVED starting_max_10_frames=1\n")
        receiver.command_sent("ARM")
        receiver.feed(synthetic_frame(1) + b"BURST_END frames=1 large_confirmed=0\n")
        receiver.finish()
        self.assertTrue(analyze_session(session)["camera_bursts"][0]["boundary_complete"])

    def test_capture_failure_aborts_and_unknown_identity_remains_unknown(self):
        _, _, result = self.record(b"VIBRATION_RECEIVED starting_max_10_frames=1\n"
                                   b"ERROR camera_capture\n")
        self.assertEqual(result["camera_bursts"][0]["status"], "aborted")
        self.assertEqual(result["counts"]["application_error_messages"], 1)
        self.assertEqual(result["provenance"]["device_identity"], "not_established")
        self.assertEqual(result["provenance"]["observed_identity_messages"], [])


class SyntheticSerialError(OSError):
    pass


class SyntheticPort:
    """SYNTHETIC stand-in for pyserial; never opens an operating-system port."""
    def __init__(self, payload=b"", *, fail_reads=False, fail_write=False, interrupt=False,
                 unexpected_error=None):
        self.payload = payload
        self.fail_reads = fail_reads
        self.fail_write = fail_write
        self.interrupt = interrupt
        self.unexpected_error = unexpected_error
        self.is_open = False
        self.written = []
        self.read_count = 0

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def write(self, data):
        if self.fail_write:
            raise SyntheticSerialError("SYNTHETIC command write failed")
        self.written.append(data)
        return len(data)

    def read(self, size):
        self.read_count += 1
        if self.payload:
            result, self.payload = self.payload[:size], self.payload[size:]
            return result
        if self.interrupt:
            raise KeyboardInterrupt
        if self.fail_reads:
            raise SyntheticSerialError("SYNTHETIC port disconnected")
        if self.unexpected_error is not None:
            raise self.unexpected_error
        return b""


class ImageReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []
        self.boxes = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.sources.append(dict(attrs).get("src"))
        if tag == "div" and dict(attrs).get("class") == "box":
            self.boxes.append(dict(attrs).get("style", ""))


class RecorderCliTests(SyntheticCase):
    def run_main(self, port, *extra):
        self.session_number += 1
        session = self.root / f"SYNTHETIC-cli-{self.session_number:03d}"
        module = types.SimpleNamespace(Serial=lambda *args, **kwargs: port,
                                       SerialException=SyntheticSerialError)
        ticks = itertools.count(0, 0.001)
        with patch.dict(sys.modules, {"serial": module}), \
                patch.object(record_photos.time, "monotonic", side_effect=lambda: next(ticks)), \
                contextlib.redirect_stdout(io.StringIO()):
            status = record_photos.main(["--output", str(session), "--seconds", "1",
                                         "--label", "SYNTHETIC", *extra])
        return status, session

    def test_fake_port_closes_manifest_and_gallery_uses_only_recorded_facts(self):
        raw = b"".join(synthetic_frame(number, photo=True) for number in range(1, 4))
        missing_cutoff = synthetic_metadata(4, 240, "SMALL_CHANGE")
        del missing_cutoff["cutoff_percent"]
        raw += (synthetic_scores(4, 240, 432) +
                synthetic_line("MOTION " + json.dumps(missing_cutoff)) + synthetic_photo(missing_cutoff))
        port = SyntheticPort(raw)
        status, session = self.run_main(port)
        self.assertEqual(status, 0)
        self.assertFalse(port.is_open)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        manifest = json.loads((session / "run_manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], 3)
        self.assertTrue(manifest["closed"])
        for artifact in manifest["artifacts"]:
            data = (session / artifact["path"]).read_bytes()
            self.assertEqual(artifact["bytes"], len(data))
            self.assertEqual(artifact["sha256"], hashlib.sha256(data).hexdigest())
        page = (session / "index.html").read_text()
        references = ImageReferences()
        references.feed(page)
        self.assertEqual(len([source for source in references.sources if source and source.endswith(".jpg")]), 4)
        self.assertTrue(all((session / source).is_file() for source in references.sources if source))
        self.assertIsNone(re.search(r"confirmation\s*:\s*[23]\s*frames", page, re.IGNORECASE))
        self.assertIn("assisted", page.lower())
        self.assertNotIn("None%", page)
        self.assertIn("not reported", page.lower())
        analysis = analyze_session(session)
        self.assertEqual(analysis["errors"], [])
        frame = next(row for row in analysis["frames"] if row["metadata"]["frame"] == 4)
        self.assertEqual(frame["metadata"]["area_percent"], 5.0)
        self.assertNotIn("cutoff_percent", frame["metadata"])
        self.assertEqual(frame["reference_selection"]["status"], "unavailable")

    def test_disconnect_preserves_prior_photo_and_reports_failure(self):
        raw = synthetic_frame(1, photo=True)
        status, session = self.run_main(SyntheticPort(raw, fail_reads=True))
        self.assertEqual(status, 1)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        self.assertEqual(len(list(session.glob("*.jpg"))), 1)
        self.assertTrue(json.loads((session / "run_manifest.json").read_text())["closed"])
        self.assertTrue(json.loads((session / "summary.json").read_text())["errors"])

    def test_failed_command_write_is_not_logged_as_sent(self):
        port = SyntheticPort(fail_write=True)
        status, session = self.run_main(port, "--arm")
        self.assertEqual(status, 1)
        self.assertEqual(port.written, [])
        rows = [json.loads(line) for line in (session / "events.jsonl").read_text().splitlines()]
        self.assertFalse(any(row.get("recorder_event") == "HOST_COMMAND" for row in rows))
        self.assertTrue(any(row.get("recorder_event") == "ERROR" for row in rows))

    def test_successful_existing_command_is_only_a_request(self):
        port = SyntheticPort(synthetic_frame(1))
        status, session = self.run_main(port, "--calibrate")
        self.assertEqual(status, 0)
        self.assertEqual(port.written, [b"BASELINE\n"])
        rows = [json.loads(line) for line in (session / "events.jsonl").read_text().splitlines()]
        commands = [row["command"] for row in rows if row.get("recorder_event") == "HOST_COMMAND"]
        self.assertEqual(commands, ["BASELINE"])
        self.assertEqual(analyze_session(session)["counts"]["calibration_frame_records"], 0)

    def test_operator_interrupt_finalizes_available_evidence(self):
        raw = synthetic_frame(1, photo=True)
        status, session = self.run_main(SyntheticPort(raw, interrupt=True))
        self.assertEqual(status, 130)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        self.assertTrue(json.loads((session / "run_manifest.json").read_text())["closed"])
        self.assertTrue((session / "summary.json").is_file())

    def test_photo_write_failure_never_claims_saved_pair(self):
        with patch.object(record_photos, "save_photo", side_effect=OSError("SYNTHETIC disk write failed")):
            status, session = self.run_main(SyntheticPort(synthetic_frame(1, photo=True)))
        self.assertEqual(status, 1)
        self.assertEqual(list(session.glob("*.jpg")), [])
        self.assertTrue((session / "serial.raw").read_bytes())
        self.assertTrue(json.loads((session / "summary.json").read_text())["errors"])

    def test_manifest_detects_mutation_and_rejects_escape(self):
        _, session = self.run_main(SyntheticPort(synthetic_frame(1, photo=True)))
        with (session / "serial.raw").open("ab") as stream:
            stream.write(b"SYNTHETIC altered artifact")
        self.assertTrue(analyze_session(session)["errors"])
        manifest_path = session / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][0]["path"] = "../SYNTHETIC-outside"
        manifest_path.write_text(json.dumps(manifest))
        result = analyze_session(session)
        self.assertTrue(any("manifest" in problem["code"] for problem in result["errors"]))

    def test_empty_stream_is_not_a_successful_recording(self):
        status, session = self.run_main(SyntheticPort())
        self.assertEqual(status, 1)
        self.assertTrue((session / "run_manifest.json").is_file())

    def test_huge_numeric_metadata_returns_failure_but_retains_later_photo(self):
        for field, sign, metadata in synthetic_huge_metadata_cases():
            with self.subTest(field=field, sign=sign):
                raw = (synthetic_line("MOTION " + json.dumps(metadata)) +
                       synthetic_frame(2, photo=True))
                port = SyntheticPort(raw)
                status, session = self.run_main(port)
                self.assertEqual(status, 1)
                self.assertFalse(port.is_open)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                result = analyze_session(session)
                self.assertEqual(result["counts"]["verified_photos"], 1)
                self.assertEqual([row["metadata"]["frame"] for row in result["frames"]], [2])
                summary_path = session / "summary.json"
                summary = json.loads(summary_path.read_text())
                self.assertTrue(summary["errors"])
                manifest = json.loads((session / "run_manifest.json").read_text())
                self.assertTrue(manifest["closed"])
                self.assertEqual(manifest["end_reason"], summary["recording_end_reason"])
                entry = next(row for row in manifest["artifacts"] if row["path"] == "summary.json")
                self.assertEqual(entry["sha256"], hashlib.sha256(summary_path.read_bytes()).hexdigest())

    def test_invalid_photo_geometry_finalizes_all_images_with_error_status(self):
        for name, geometry in synthetic_invalid_photo_geometry():
            with self.subTest(case=name):
                metadata = {"frame": 1, "state": "SMALL_CHANGE", "area_percent": 7.271,
                            "jpeg_bytes": len(SYNTHETIC_JPEG), "fnv1a": fnv1a(SYNTHETIC_JPEG),
                            **geometry}
                raw = synthetic_photo(metadata) + synthetic_frame(2, 384, "CONFIRMING", photo=True)
                port = SyntheticPort(raw)
                status, session = self.run_main(port)
                self.assertEqual(status, 1)
                self.assertFalse(port.is_open)
                self.assertEqual((session / "serial.raw").read_bytes(), raw)
                summary_path = session / "summary.json"
                summary = json.loads(summary_path.read_text())
                self.assertEqual(summary["counts"]["verified_photos"], 2)
                self.assertTrue(any(problem["code"] == "invalid_photo_geometry" for problem in summary["errors"]))
                manifest = json.loads((session / "run_manifest.json").read_text())
                self.assertTrue(manifest["closed"])
                self.assertEqual(manifest["end_reason"], summary["recording_end_reason"])
                for artifact in manifest["artifacts"]:
                    self.assertEqual(artifact["sha256"], hashlib.sha256((session / artifact["path"]).read_bytes()).hexdigest())
                references = ImageReferences()
                references.feed((session / "index.html").read_text())
                self.assertEqual(len(references.sources), 2)
                self.assertEqual(len(references.boxes), 1)
                self.assertFalse(any(problem["code"].startswith("manifest") for problem in analyze_session(session)["errors"]))

    def test_unexpected_failure_is_finalized_truthfully_and_reraised(self):
        raw = synthetic_frame(1, photo=True)
        failure = RuntimeError("SYNTHETIC unexpected recorder failure")
        port = SyntheticPort(raw, unexpected_error=failure)
        with self.assertRaises(RuntimeError) as caught:
            self.run_main(port)
        self.assertIs(caught.exception, failure)
        session = self.root / f"SYNTHETIC-cli-{self.session_number:03d}"
        self.assertFalse(port.is_open)
        self.assertEqual((session / "serial.raw").read_bytes(), raw)
        self.assertEqual(analyze_session(session)["counts"]["verified_photos"], 1)
        rows = event_rows(session)
        failures = [row for row in rows if row.get("recorder_event") == "ERROR"
                    and row.get("code") == "unexpected_error"]
        self.assertEqual(len(failures), 1)
        self.assertIn("RuntimeError", failures[0]["detail"])
        self.assertIn("SYNTHETIC unexpected recorder failure", failures[0]["detail"])
        summary = json.loads((session / "summary.json").read_text())
        manifest = json.loads((session / "run_manifest.json").read_text())
        self.assertTrue(summary["errors"])
        self.assertEqual(summary["recording_end_reason"], "unexpected_error")
        self.assertEqual(manifest["end_reason"], "unexpected_error")
        self.assertTrue(manifest["closed"])


class RetainedNightSessionTests(unittest.TestCase):
    """Read-only regression; this is retained evidence, never a synthetic wire stream."""
    def test_preserves_real_chunk_boundaries_scores_and_unknown_provenance(self):
        files = sorted(path for path in NIGHT_SESSION.iterdir() if path.is_file())
        before = {path.name: file_identity(path) for path in files}
        def check_source_unchanged():
            after_files = sorted(path for path in NIGHT_SESSION.iterdir() if path.is_file())
            self.assertEqual({path.name: file_identity(path) for path in after_files}, before)
        self.addCleanup(check_source_unchanged)
        self.assertEqual(len(files), 39)
        result = analyze_session(NIGHT_SESSION)
        self.assertEqual(SCHEMA_VERSION, 3)
        counts = result["counts"]
        expected = {
            "motion_frame_records": 18, "detector_frame_records": 18,
            "photos_saved": 18, "verified_photos": 18,
            "detection_score_records": 18, "paired_score_records": 18,
            "pir_wait_openings": 2, "camera_bursts": 2,
            "complete_camera_bursts": 2, "fully_observed_wait_to_capture_sequences": 1,
            "unresolved_waits": 1, "alarm_start_messages": 1, "alarm_stop_messages": 1,
            "sdk_error_diagnostics": 2, "application_error_messages": 0,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(counts[key], value)
        self.assertEqual(result["detector_state_counts"],
                         {"SMALL_CHANGE": 12, "CLEAR": 4, "CONFIRMING": 1, "LARGE_CHANGE": 1})
        self.assertEqual([burst["start_line"] for burst in result["camera_bursts"]], [1, 61])
        self.assertEqual([burst["end_line"] for burst in result["camera_bursts"]], [34, 97])
        self.assertEqual([burst["declared_attempts"] for burst in result["camera_bursts"]], [8, 10])
        self.assertIsNone(result["camera_bursts"][0]["preceding_wait"])
        self.assertEqual([wait["start_line"] for wait in result["waits"]], [52, 103])
        self.assertEqual([wait["outcome"] for wait in result["waits"]], ["received", "unresolved"])
        frames = {row["metadata"]["frame"]: row for row in result["frames"]}
        self.assertEqual(frames[53]["line"], 33)
        self.assertEqual(frames[53]["score_event_line"], 32)
        self.assertEqual(frames[53]["alarm_start_lines"], [31])
        self.assertEqual(frames[52]["scores"]["grayscale_percent"], 7.271)
        self.assertEqual(frames[53]["scores"]["assisted_percent"], 9.417)
        self.assertTrue(all(row["scores"]["color_enabled"] == 1 for row in frames.values()))
        self.assertTrue(all(row["scores"]["assisted_percent"] < 10 for row in frames.values()))
        self.assertEqual(result["last_observed_status"]["line"], 102)
        self.assertEqual(result["last_observed_status"]["followed_by_event_records"], 1)
        self.assertFalse(result["provenance"]["raw_present"])
        self.assertEqual(result["provenance"]["device_identity"], "not_established")
        self.assertEqual(result["provenance"]["observed_identity_messages"], [])
        self.assertFalse(result["errors"])
        summary = summary_from_analysis(result, "retained-night-evidence")
        self.assertEqual(summary["schema_version"], 3)
        self.assertNotIn("measured_frames", summary)


if __name__ == "__main__":
    unittest.main()
