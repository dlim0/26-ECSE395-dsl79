"""Read current detector evidence without replaying an image-processing gate.

Observed waits, camera boundaries, transferred bytes and source-based attempt
accounting are separate facts. Reading a session never changes its artifacts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

SCHEMA_VERSION = 3
REFERENCE_REVISION = "c192410a2788974f9356570ec7a4527fd893a296"
DETECTOR_STATES = frozenset({"CLEAR", "SMALL_CHANGE", "CONFIRMING", "WAITING_FOR_GROWTH", "LARGE_CHANGE"})
CALIBRATION_STATES = frozenset({"SETTLING", "CALIBRATING"})
DIAGNOSTIC_STATES = frozenset({"CAMERA_TEST", "LARGE_CHANGE_TEST_ONLY"})
REGION_STATES = DETECTOR_STATES | {"LARGE_CHANGE_TEST_ONLY"}
HOST_FIELDS = frozenset({"host_received", "test_label", "record_schema", "motion_event_sequence", "_host"})
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SDK_DIAGNOSTIC = re.compile(r"^([EW])\s+\(\s*\d+\)")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            reject(value)
        return number

    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject, parse_float=finite_float)


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f"{value:08x}"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _finite(value):
    # Python integers are finite but need not fit in a float. Range checks
    # must reject oversized percentages before mixed float/int arithmetic.
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_frame(item, *, detector=None):
    if not isinstance(item, dict):
        raise ValueError("Frame metadata must be an object")
    if not is_integer(item.get("frame")) or not 0 <= item["frame"] <= 0xffffffff:
        raise ValueError("Invalid frame number")
    if not isinstance(item.get("state"), str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", item["state"]):
        raise ValueError("Invalid frame state")
    if "area_percent" in item and (not _finite(item["area_percent"]) or not 0 <= item["area_percent"] <= 100):
        raise ValueError("Invalid area percentage")
    if "cutoff_percent" in item and (not _finite(item["cutoff_percent"]) or not 0 < item["cutoff_percent"] <= 100):
        raise ValueError("Invalid selected cutoff")
    if detector is None:
        detector = item["state"] in REGION_STATES
    if detector:
        if item.get("grid") != [80, 60]:
            raise ValueError("Detector grid must be 80 by 60")
        box = item.get("bbox")
        if not isinstance(box, list) or len(box) != 4 or not all(is_integer(v) for v in box):
            raise ValueError("Invalid bounding box")
        x, y, width, height = box
        pixels = item.get("changed_pixels")
        if not is_integer(pixels) or not 0 <= pixels <= 4800:
            raise ValueError("Invalid changed-pixel area")
        if min(box) < 0 or x + width > 80 or y + height > 60 or pixels > width * height:
            raise ValueError("Region exceeds its grid or bounding box")
        area = item.get("area_percent")
        if not _finite(area) or not 0 <= area <= 100 or abs(area - pixels * 100 / 4800) > 0.000501:
            raise ValueError("Area percentage disagrees with changed_pixels")
    return item


def validate_photo_metadata(item):
    # A valid photo-only header need not contain a complete detector measurement.
    validate_frame(item, detector=False)
    if not is_integer(item.get("jpeg_bytes")) or not 0 < item["jpeg_bytes"] <= 500000:
        raise ValueError("Invalid JPEG length")
    if not isinstance(item.get("fnv1a"), str) or not re.fullmatch(r"[0-9a-fA-F]{8}", item["fnv1a"]):
        raise ValueError("Invalid FNV-1a checksum")
    return item


def photo_geometry(item):
    """Interpret optional region geometry separately from photo-byte integrity.

    Keep the received values unchanged. Exact ratios avoid float overflow even
    when finite JSON integers are too large to convert to floats individually.
    """
    if "bbox" not in item and "grid" not in item:
        return {"status": "not_reported"}
    box, grid = item.get("bbox"), item.get("grid")
    if not isinstance(box, list) or len(box) != 4 or not isinstance(grid, list) or len(grid) != 2:
        return {"status": "invalid", "detail": "Geometry requires a four-value bbox and two-value grid"}
    if not all(_finite(value) for value in box + grid):
        return {"status": "invalid", "detail": "Geometry values must be finite numbers, excluding booleans"}
    x, y, width, height = (Fraction(value) for value in box)
    columns, rows = (Fraction(value) for value in grid)
    if columns <= 0 or rows <= 0:
        return {"status": "invalid", "detail": "Geometry grid dimensions must be positive"}
    if min(x, y, width, height) < 0 or x + width > columns or y + height > rows:
        return {"status": "invalid", "detail": "Geometry bbox extends outside its grid"}
    if width == 0 or height == 0:
        return {"status": "empty"}
    return {"status": "valid",
            "percent_bounds": [float(value / extent) * 100
                               for value, extent in ((x, columns), (y, rows), (width, columns), (height, rows))]}


def device_metadata(item):
    return {key: value for key, value in item.items() if key not in HOST_FIELDS}


def _fields(message):
    result = {}
    for key, value in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", message):
        if key in result:
            raise ValueError(f"Duplicate message field: {key}")
        result[key] = value
    return result


def _unsigned(text, label):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+", text):
        raise ValueError(f"Invalid {label}")
    value = int(text)
    if value > 0xffffffff:
        raise ValueError(f"Invalid {label}")
    return value


def parse_detection_scores(message):
    clean = ANSI.sub("", message).strip()
    if not clean.startswith("DETECTION_SCORES "):
        raise ValueError("Not a DETECTION_SCORES message")
    values = _fields(clean)
    required = {"frame", "grayscale_percent", "assisted_percent", "color_enabled", "grayscale_cutoff", "color_cutoff"}
    if not required <= values.keys():
        raise ValueError("Incomplete DETECTION_SCORES fields")
    result = {"frame": _unsigned(values["frame"], "score frame")}
    for name in ("grayscale_percent", "assisted_percent", "grayscale_cutoff", "color_cutoff"):
        try:
            value = float(values[name])
        except ValueError as exc:
            raise ValueError(f"Invalid {name}") from exc
        if not math.isfinite(value) or not 0 <= value <= 100 or (name.endswith("cutoff") and value == 0):
            raise ValueError(f"Invalid {name}")
        result[name] = value
    if values["color_enabled"] not in {"0", "1"}:
        raise ValueError("Invalid color_enabled; expected 0 or 1")
    result["color_enabled"] = values["color_enabled"] == "1"
    result.update({key: value for key, value in values.items() if key not in required})
    return result


def parse_device_message(message):
    """Classify observed variants, without guessing a global firmware mode."""
    clean = ANSI.sub("", message).strip()
    event = clean.split(maxsplit=1)[0] if clean else ""
    structured = {"DETECTION_SCORES", "PIR_TRIGGER", "VIBRATION_RECEIVED", "VIBRATION_TIMEOUT",
                  "BURST_END", "DETERRENT_ON", "DETERRENT_OFF", "STATUS", "ARMED"}
    values = _fields(clean) if event in structured else {}
    result = {"kind": "message", "fields": values, "clean": clean}
    if event == "DETECTION_SCORES":
        return result | {"kind": "scores", "scores": parse_detection_scores(clean)}
    if event == "BOOT":
        result["kind"] = "boot"
    elif clean.startswith("ARMED manual_rearm=") or clean.startswith(("CALIBRATION clear_view", "CALIBRATION complete")):
        result["kind"] = "reset"
    elif event == "PIR_TRIGGER" and "waiting_for_vibration_s" in values:
        seconds = _unsigned(values["waiting_for_vibration_s"], "vibration wait")
        if seconds == 0:
            raise ValueError("Vibration wait must be positive")
        result.update(kind="wait_start", reported_seconds=seconds)
    elif event == "PIR_TRIGGER" and values.get("starting_max_10_frames") == "1":
        if values.get("test") == "PIR_WIFI_CAMERA":
            result.update(kind="capture_start", start_kind="pir_test")
        elif "test" not in values:
            result.update(kind="capture_start", start_kind="pir_direct")
    elif event == "VIBRATION_RECEIVED" and values.get("starting_max_10_frames") == "1":
        result.update(kind="capture_start", start_kind="vibration")
    elif event == "VIBRATION_TIMEOUT":
        result["kind"] = "wait_timeout"
    elif event == "BURST_END":
        attempts = _unsigned(values.get("frames"), "burst attempt count")
        if values.get("large_confirmed") not in {"0", "1"}:
            raise ValueError("Invalid burst confirmation")
        result.update(kind="capture_end", declared_attempts=attempts, reported_confirmation=int(values["large_confirmed"]))
    elif clean == "ERROR jpeg_decode" or clean.startswith("ERROR jpeg_decode "):
        result["kind"] = "decode_error"
    elif clean.startswith(("ERROR camera_wake", "ERROR camera_capture", "BURST_ABORT")):
        result["kind"] = "capture_abort"
    elif event == "DETERRENT_ON":
        result.update(kind="alarm_on", frame=_unsigned(values["frame"], "alarm frame") if "frame" in values else None)
    elif event == "DETERRENT_OFF":
        result["kind"] = "alarm_off"
    elif event == "STATUS":
        result["kind"] = "status"
    return result


def _host_sequence(metadata):
    host = metadata.get("_host")
    return host.get("sequence") if isinstance(host, dict) else None


def analyze_session(directory, *, read_saved_summary=True, verify_manifest=True):
    """Return schema-3 observations; do not write or reconstruct missing input."""
    root = Path(directory).resolve()
    event_path = root / "events.jsonl"
    manifest_present = (root / "run_manifest.json").is_file()
    errors, warnings, reference_warnings = [], [], []
    frames, waits, bursts, alarms, application_errors, diagnostics = [], [], [], [], [], []
    pending_scores = defaultdict(list)
    photo_receipts, host_sequences = defaultdict(list), defaultdict(list)
    active_photo_begin = None
    has_receipt_events = False
    observed_identity = []
    counts = Counter({name: 0 for name in (
        "motion_frame_records", "detector_frame_records", "calibration_frame_records",
        "diagnostic_frame_records", "unknown_frame_records", "detection_score_records",
        "paired_score_records", "alarm_start_messages", "alarm_stop_messages",
        "sdk_error_diagnostics", "sdk_warning_diagnostics", "pir_wait_openings")})
    epoch, active_wait, active_burst, last_status, last_event = 0, None, None, None, None
    line_count = 0

    def issue(collection, code, line, detail):
        collection.append({"code": code, "line": line, "detail": detail})

    def close_wait(outcome, line):
        nonlocal active_wait
        if active_wait is not None:
            active_wait.update(outcome=outcome, end_line=line)
            active_wait = None

    def close_burst(reason, line, status="aborted", ending=None):
        nonlocal active_burst
        if active_burst is None:
            if ending is None:
                return
            open_burst(None, "unobserved")
            active_burst["issues"].append("missing_capture_start")
        active_burst.update(end_line=line, end_reason=reason, status=status,
                            boundary_complete=bool(active_burst["start_observed"] and ending is not None))
        if ending:
            active_burst["declared_attempts"] = ending["declared_attempts"]
            active_burst["reported_confirmation"] = ending["reported_confirmation"]
        active_burst = None

    def open_burst(line, kind):
        nonlocal active_burst
        active_burst = {"number": len(bursts) + 1, "start_line": line, "start_observed": line is not None,
                        "start_kind": kind, "preceding_wait": None, "epoch": epoch,
                        "end_line": None, "end_reason": None, "status": "unfinished", "boundary_complete": False,
                        "frame_lines": [], "observed_motion_records": 0, "observed_decode_errors": 0,
                        "declared_attempts": None, "reported_confirmation": None, "issues": [], "_ledger": []}
        bursts.append(active_burst)

    # Decode inside strict_json's guarded block, so a damaged JSONL byte line
    # is an integrity finding instead of interrupting analysis of later rows.
    with event_path.open("rb") as stream:
        for line_count, raw in enumerate(stream, 1):
            try:
                row = strict_json(raw)
                if not isinstance(row, dict):
                    raise ValueError("Event must be an object")
            except (ValueError, TypeError) as exc:
                issue(errors, "invalid_event_json", line_count, str(exc))
                if active_burst:
                    active_burst["issues"].append("invalid_event_json")
                continue
            last_event = {"line": line_count, "record": row}
            if "_host" in row or row.get("recorder_event") in {"PHOTO_BEGIN", "PHOTO_SAVED"}:
                has_receipt_events = True
            sequence = _host_sequence(row)
            if is_integer(sequence) and sequence > 0:
                host_sequences[sequence].append(line_count)
            if "frame" in row and "recorder_event" not in row:
                try:
                    validate_frame(row)
                except ValueError as exc:
                    issue(errors, "invalid_frame_metadata", line_count, str(exc))
                    if active_burst:
                        active_burst["issues"].append("invalid_frame_metadata")
                    continue
                state = row["state"]
                kind = ("detector" if state in DETECTOR_STATES else "calibration" if state in CALIBRATION_STATES
                        else "diagnostic" if state in DIAGNOSTIC_STATES else "unknown")
                counts["motion_frame_records"] += 1
                counts[kind + "_frame_records"] += 1
                frame = {"line": line_count, "metadata": row, "kind": kind, "epoch": epoch,
                         "burst": active_burst["number"] if active_burst else None,
                         "scores": None, "score_event_line": None, "score_association": "missing", "alarm_start_lines": []}
                candidates = pending_scores.pop((epoch, row["frame"]), [])
                if len(candidates) == 1:
                    frame.update(scores=candidates[0]["scores"], score_event_line=candidates[0]["line"], score_association="matched")
                    counts["paired_score_records"] += 1
                elif candidates:
                    frame["score_association"] = "ambiguous"
                    issue(errors, "ambiguous_detection_scores", line_count,
                          f"Frame {row['frame']} has multiple preceding score records at lines {[s['line'] for s in candidates]}")
                elif kind in {"detector", "diagnostic"}:
                    issue(warnings, "missing_detection_scores", line_count, "No unambiguous preceding auxiliary scores; selected metadata retained")
                if frame["scores"] is not None and state in REGION_STATES:
                    scores = frame["scores"]
                    selection = {"revision": REFERENCE_REVISION, "status": "unavailable", "running_binary_verified": False}
                    if scores["grayscale_cutoff"] == 7 and scores["color_cutoff"] == 10 and "cutoff_percent" in row:
                        gray_pass = scores["grayscale_percent"] >= 7
                        assisted_pass = scores["color_enabled"] and scores["assisted_percent"] >= 10
                        use_assisted = assisted_pass and not gray_pass
                        expected_area = scores["assisted_percent"] if use_assisted else scores["grayscale_percent"]
                        expected_cutoff = 10 if use_assisted else 7
                        matches = (abs(row["area_percent"] - expected_area) <= 0.001
                                   and row.get("cutoff_percent") == expected_cutoff
                                   and (scores["color_enabled"] or scores["assisted_percent"] == 0))
                        selection.update(status="matched" if matches else "mismatch",
                                         selected_metric="assisted_union" if use_assisted else "grayscale",
                                         expected_area_percent=expected_area, expected_cutoff_percent=expected_cutoff)
                        if not matches:
                            issue(reference_warnings, "selected_region_reference_mismatch", line_count,
                                  "Selected metadata/auxiliary scores differ from the named source contract; received values remain unchanged")
                    frame["reference_selection"] = selection
                frames.append(frame)
                if active_burst:
                    active_burst["frame_lines"].append(line_count)
                    active_burst["observed_motion_records"] += 1
                    active_burst["_ledger"].append(("frame", row["frame"], line_count))
                continue
            if "recorder_event" in row:
                if row["recorder_event"] == "PHOTO_BEGIN":
                    active_photo_begin = {"line": line_count, "epoch": epoch, "record": row}
                elif row["recorder_event"] == "PHOTO_SAVED":
                    if isinstance(row.get("metadata_file"), str):
                        photo_receipts[row["metadata_file"]].append(
                            {"line": line_count, "epoch": epoch, "record": row, "begin": active_photo_begin})
                    active_photo_begin = None
                elif row["recorder_event"] == "ERROR":
                    issue(errors, "recorder_error", line_count, row.get("detail", row.get("code", "Recorder error")))
                    if row.get("code") in {"photo_interrupted", "photo_oversized", "photo_rejected", "photo_incomplete",
                                          "invalid_photo_header", "photo_interrupted_by_boot", "serial_line_too_long"}:
                        active_photo_begin = None
                    if active_burst and row.get("code") in {"invalid_motion", "invalid_utf8", "serial_line_too_long"}:
                        active_burst["issues"].append("lost_measurement_context")
                elif row["recorder_event"] in {"TRAILING_FRAGMENT", "PHOTO_FRAGMENT"}:
                    issue(warnings, "partial_serial_capture", line_count, row.get("detail", row["recorder_event"]))
                continue
            message = row.get("device_message")
            if not isinstance(message, str):
                issue(warnings, "unknown_event_record", line_count, "Event has no recognized payload; retained without interpretation")
                continue
            clean = ANSI.sub("", message).strip()
            sdk = SDK_DIAGNOSTIC.match(clean)
            if sdk:
                diagnostics.append({"line": line_count, "level": sdk.group(1), "message": message})
                counts["sdk_error_diagnostics" if sdk.group(1) == "E" else "sdk_warning_diagnostics"] += 1
            if clean == "ERROR" or clean.startswith("ERROR "):
                application_errors.append({"line": line_count, "message": message})
            if clean.startswith(("BOOT ", "READY ", "DETECTION_MODE ")):
                observed_identity.append({"line": line_count, "message": message})
            if clean.startswith("DETECTION_SCORES "):
                counts["detection_score_records"] += 1
            try:
                parsed = parse_device_message(message)
            except ValueError as exc:
                issue(errors, "invalid_device_message", line_count, str(exc))
                if active_burst:
                    active_burst["issues"].append("invalid_device_message")
                continue
            kind = parsed["kind"]
            if kind == "scores":
                pending_scores[(epoch, parsed["scores"]["frame"])].append({"line": line_count, "scores": parsed["scores"]})
            elif kind in {"boot", "reset"}:
                close_wait("reset", line_count)
                close_burst("BOOT" if kind == "boot" else clean.split()[0], line_count)
                if kind == "boot":
                    active_photo_begin = None
                    epoch += 1
            elif kind == "wait_start":
                close_wait("replaced", line_count)
                close_burst("NEW_WAIT", line_count)
                active_wait = {"number": len(waits) + 1, "start_line": line_count, "end_line": None,
                               "outcome": "unresolved", "reported_seconds": parsed["reported_seconds"], "burst": None}
                waits.append(active_wait)
                counts["pir_wait_openings"] += 1
            elif kind == "wait_timeout":
                if active_wait is None:
                    issue(warnings, "unmatched_vibration_timeout", line_count, "Timeout retained without an observed wait opening")
                close_wait("timed_out", line_count)
            elif kind == "capture_start":
                close_burst("NEW_CAPTURE_START", line_count)
                open_burst(line_count, parsed["start_kind"])
                if parsed["start_kind"] == "vibration" and active_wait is not None:
                    active_burst["preceding_wait"] = active_wait["number"]
                    active_wait["burst"] = active_burst["number"]
                    close_wait("received", line_count)
                else:
                    if active_wait is not None:
                        close_wait("reset", line_count)
                    if parsed["start_kind"] == "vibration":
                        issue(warnings, "missing_preceding_pir_wait", line_count, "Camera start observed; preceding PIR/wait is unavailable")
            elif kind == "capture_end":
                close_burst("BURST_END", line_count, "ended", parsed)
            elif kind == "decode_error":
                if active_burst:
                    active_burst["observed_decode_errors"] += 1
                    active_burst["_ledger"].append(("decode_error", None, line_count))
                    # No invented failed frame ID and no universal abort: only
                    # the named current vibration contract says it may continue.
                else:
                    issue(warnings, "unbound_decode_error", line_count, "No observed active camera burst for this error")
            elif kind == "capture_abort":
                close_burst(clean.split()[0], line_count)
            elif kind == "alarm_on":
                counts["alarm_start_messages"] += 1
                alarms.append({"line": line_count, "message": message, "frame": parsed["frame"], "epoch": epoch,
                               "burst": active_burst["number"] if active_burst else None,
                               "matching_frame_lines": [], "association": "missing"})
            elif kind == "alarm_off":
                counts["alarm_stop_messages"] += 1
            elif kind == "status":
                last_status = {"line": line_count, "message": message}
            elif "MOTION {" in clean:
                issue(warnings, "embedded_unparsed_motion", line_count, "Embedded MOTION text was not inserted as an assumed measurement")

    # Preserve EOF as an observation boundary, not a fabricated device event.
    if active_burst is not None:
        active_burst["end_reason"] = "END_OF_RECORDING"
    for candidates in pending_scores.values():
        for candidate in candidates:
            issue(warnings, "orphan_detection_scores", candidate["line"], "Auxiliary scores have no unambiguous subsequent MOTION receipt")
    for alarm in alarms:
        matches = [frame for frame in frames if frame["epoch"] == alarm["epoch"] and frame["metadata"]["frame"] == alarm["frame"]
                   and (alarm["burst"] is None or frame["burst"] == alarm["burst"])]
        alarm["matching_frame_lines"] = [frame["line"] for frame in matches]
        alarm["association"] = "matched" if len(matches) == 1 else "ambiguous" if matches else "missing"
        if len(matches) == 1:
            matches[0]["alarm_start_lines"].append(alarm["line"])
        else:
            issue(warnings, "unpaired_alarm_start", alarm["line"], "Software alarm retained without a unique received frame; physical output is not established")
    for burst in bursts:
        ledger = burst.pop("_ledger")
        accounted = burst["observed_motion_records"] + burst["observed_decode_errors"]
        reference = {"revision": REFERENCE_REVISION, "contract": "vibration capture: MOTION successes plus observed JPEG decode failures consume attempts",
                     "status": "unavailable", "observed_attempt_records": accounted,
                     "declared_attempts": burst["declared_attempts"], "sequence_issues": [], "running_binary_verified": False}
        if burst["boundary_complete"] and burst["start_kind"] in {"vibration", "pir_test"} and not burst["issues"]:
            previous, failed = None, 0
            for item_kind, number, event_line in ledger:
                if item_kind == "decode_error":
                    failed += 1
                else:
                    if previous is not None and number != previous + failed + 1:
                        reference["sequence_issues"].append({"line": event_line, "code": "frame_sequence_not_accounted"})
                    previous, failed = number, 0
            reference["status"] = "matched" if accounted == burst["declared_attempts"] and not reference["sequence_issues"] else "mismatch"
            if reference["status"] == "mismatch":
                issue(reference_warnings, "attempt_accounting_mismatch", burst["end_line"],
                      "Received counts/sequence differ from the named reference contract; original observations are retained")
        burst["reference_accounting"] = reference

    photos = []
    for metadata_path in sorted(root.glob("frame*.json")):
        photo = {"metadata_file": metadata_path.name, "image_file": metadata_path.with_suffix(".jpg").name,
                 "checksum_verified": False, "matching_event_lines": []}
        try:
            metadata = strict_json(metadata_path.read_text(encoding="utf-8"))
            validate_photo_metadata(metadata)
            image_path = metadata_path.with_suffix(".jpg")
            data = image_path.read_bytes()
            if len(data) != metadata["jpeg_bytes"] or fnv1a(data).lower() != metadata["fnv1a"].lower():
                raise ValueError("JPEG length/checksum mismatch")
            if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                raise ValueError("Incomplete JPEG markers")
            matches = []
            binding_problem = None
            receipts = photo_receipts.get(metadata_path.name, [])
            receipt_format = manifest_present or has_receipt_events or bool(receipts) or any(
                key in metadata for key in ("record_schema", "motion_event_sequence", "_host"))
            if not receipt_format:
                # Original sidecars have no host receipt binding. Their exact
                # metadata match is useful, but is never a fallback for a
                # newer sidecar whose binding is missing, null or invalid.
                matches = [frame for frame in frames if device_metadata(frame["metadata"]) == device_metadata(metadata)]
                photo["binding_method"] = "legacy_metadata"
            elif "motion_event_sequence" not in metadata:
                binding_problem = "Receipt-format sidecar has no motion_event_sequence"
            elif metadata["motion_event_sequence"] is None:
                photo["binding_method"] = "explicitly_unpaired"
                if any(receipt["record"].get("motion_event_sequence") is not None for receipt in receipts):
                    binding_problem = "Explicit null binding disagrees with PHOTO_SAVED receipt"
            else:
                binding = metadata["motion_event_sequence"]
                if not is_integer(binding) or binding <= 0:
                    binding_problem = "motion_event_sequence must be a positive integer or null"
                elif len(receipts) != 1:
                    binding_problem = "Binding lacks a unique canonical PHOTO_SAVED receipt"
                else:
                    receipt = receipts[0]
                    saved, begin = receipt["record"], receipt["begin"]
                    candidates = [frame for frame in frames if _host_sequence(frame["metadata"]) == binding
                                  and device_metadata(frame["metadata"]) == device_metadata(metadata)]
                    begin_sequence = _host_sequence(begin["record"]) if begin else None
                    saved_sequence = _host_sequence(saved)
                    valid_receipts = (len(candidates) == 1 and begin is not None
                                      and isinstance(begin["record"].get("metadata"), dict)
                                      and is_integer(begin_sequence) and is_integer(saved_sequence)
                                      and 0 < binding < begin_sequence < saved_sequence
                                      and host_sequences[binding] == [candidates[0]["line"]])
                    if valid_receipts:
                        valid_receipts = (host_sequences[begin_sequence] == [begin["line"]]
                                          and host_sequences[saved_sequence] == [receipt["line"]]
                                          and candidates[0]["epoch"] == begin["epoch"] == receipt["epoch"]
                                          and candidates[0]["line"] < begin["line"] < receipt["line"]
                                          and saved.get("image_file") == photo["image_file"]
                                          and is_integer(begin["record"].get("frame"))
                                          and begin["record"]["frame"] == metadata["frame"]
                                          and is_integer(saved.get("motion_event_sequence"))
                                          and saved["motion_event_sequence"] == binding
                                          and device_metadata(begin["record"]["metadata"]) == device_metadata(metadata))
                    if valid_receipts:
                        matches = candidates
                        photo["binding_method"] = "validated_receipt"
                    else:
                        binding_problem = "Binding disagrees with canonical MOTION/PHOTO_BEGIN/PHOTO_SAVED identity, epoch or order"
            if binding_problem:
                photo["binding_method"] = "invalid_receipt"
                issue(errors, "invalid_photo_binding", None, f"{metadata_path.name}: {binding_problem}; verified image retained unpaired")
            photo.update(metadata=metadata, frame=metadata["frame"], state=metadata["state"], checksum_verified=True,
                         sha256=sha256_file(image_path), matching_event_lines=[frame["line"] for frame in matches])
            photo["geometry"] = photo_geometry(metadata)
            if photo["geometry"]["status"] == "invalid":
                issue(errors, "invalid_photo_geometry", None,
                      f"{metadata_path.name}: {photo['geometry']['detail']}; verified image and original metadata retained without an overlay")
            if len(matches) != 1:
                issue(warnings, "photo_without_unique_motion", None, f"{metadata_path.name}: verified photo retained separately from measurement history")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issue(errors, "photo_integrity", None, f"{metadata_path.name}: {exc}")
        photos.append(photo)
    for image_path in root.glob("frame*.jpg"):
        if not image_path.with_suffix(".json").is_file():
            issue(errors, "image_without_metadata", None, image_path.name)

    manifest_status = {"present": manifest_present, "verified_artifacts": 0}
    if verify_manifest and manifest_status["present"]:
        try:
            manifest = strict_json((root / "run_manifest.json").read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("Unsupported run-manifest schema")
            if not isinstance(manifest.get("artifacts"), list) or type(manifest.get("closed")) is not bool:
                raise ValueError("Invalid run-manifest fields")
            artifact_paths = set()
            if not manifest["closed"]:
                issue(warnings, "open_run_manifest", None, "Capture manifest is not closed")
            for artifact in manifest["artifacts"]:
                relative = Path(artifact["path"])
                if str(relative) in artifact_paths:
                    raise ValueError("Duplicate artifact path")
                artifact_paths.add(str(relative))
                target = (root / relative).resolve()
                if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(root):
                    raise ValueError("Manifest artifact path escapes the session")
                if not is_integer(artifact["bytes"]) or artifact["bytes"] < 0 or not isinstance(artifact["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
                    raise ValueError("Invalid artifact length/hash")
                if target.stat().st_size != artifact["bytes"] or sha256_file(target) != artifact["sha256"]:
                    issue(errors, "manifest_artifact_mismatch", None, str(relative))
                else:
                    manifest_status["verified_artifacts"] += 1
            if manifest["closed"]:
                required = {"events.jsonl", "serial.raw"} | {p.name for p in root.iterdir() if p.is_file() and p.name != "run_manifest.json"}
                for missing in sorted(required - artifact_paths):
                    issue(errors, "manifest_missing_artifact", None, missing)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issue(errors, "invalid_run_manifest", None, str(exc))
    if read_saved_summary and (root / "summary.json").is_file():
        try:
            saved = strict_json((root / "summary.json").read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("Saved summary is not an object")
            if saved.get("schema_version", 1) == 1:
                for detail in saved.get("errors", []):
                    issue(warnings, "legacy_recording_error", None, str(detail))
        except (OSError, ValueError, TypeError) as exc:
            issue(warnings, "unreadable_saved_summary", None, str(exc))
    counts.update(photos_saved=len(photos), verified_photos=sum(photo["checksum_verified"] for photo in photos),
                  camera_bursts=len(bursts), complete_camera_bursts=sum(b["boundary_complete"] for b in bursts),
                  fully_observed_wait_to_capture_sequences=sum(b["preceding_wait"] is not None and b["boundary_complete"] for b in bursts),
                  unresolved_waits=sum(wait["outcome"] == "unresolved" for wait in waits),
                  application_error_messages=len(application_errors))
    if last_status:
        last_status["followed_by_event_records"] = line_count - last_status["line"]
    return {"schema_version": SCHEMA_VERSION, "session": root.name, "source_directory": str(root),
            "events_sha256": sha256_file(event_path), "event_records": line_count, "counts": dict(counts),
            "frames": frames, "photos": photos, "waits": waits, "camera_bursts": bursts, "software_alarms": alarms,
            "detector_state_counts": dict(Counter(f["metadata"]["state"] for f in frames if f["kind"] == "detector")),
            "diagnostic_state_counts": dict(Counter(f["metadata"]["state"] for f in frames if f["kind"] == "diagnostic")),
            "last_observed_status": last_status, "last_event": last_event,
            "errors": errors, "warnings": warnings, "reference_warnings": reference_warnings,
            "application_errors": application_errors, "sdk_diagnostics": diagnostics, "run_manifest": manifest_status,
            "provenance": {"raw_present": (root / "serial.raw").is_file(), "device_identity": "not_established",
                           "observed_identity_messages": observed_identity,
                           "epoch_meaning": "Observed BOOT boundaries only; epoch zero has no assumed boot identity"},
            "physical_outputs": "Software messages do not verify physical sound or light output.",
            "interpretation": "Preserved frames and camera bursts are not independent accuracy trials; no image-processing or decision gate was replayed."}


def summary_from_analysis(analysis, label):
    keep = ("schema_version", "counts", "detector_state_counts", "diagnostic_state_counts", "waits", "camera_bursts",
            "software_alarms", "last_observed_status", "last_event", "errors", "warnings", "reference_warnings",
            "application_errors", "sdk_diagnostics", "provenance", "physical_outputs", "interpretation")
    return {key: analysis[key] for key in keep} | {"label": label}
