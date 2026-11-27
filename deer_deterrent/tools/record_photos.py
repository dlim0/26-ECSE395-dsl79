"""Retain detector serial evidence and verified photo transfers (schema 3).

This recorder does not run a decision gate or verify physical sound/light output.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from recording import (SCHEMA_VERSION, analyze_session, device_metadata, fnv1a,
                       photo_geometry, sha256_file, strict_json, summary_from_analysis,
                       validate_frame, validate_photo_metadata)

TOOLS = Path(__file__).resolve().parent
REPOSITORY = TOOLS.parent
MAX_SERIAL_LINE = 800000
MAX_ENCODED_PHOTO = 700000


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_photo(root, metadata, encoded, ending):
    """Check transport bytes before saving; preserve existing and partial files."""
    root = Path(root)
    validate_photo_metadata(metadata)
    if str(metadata["frame"]) != ending.strip():
        raise ValueError("Photo frame number mismatch")
    photo = base64.b64decode("".join(encoded), validate=True)
    if len(photo) != metadata["jpeg_bytes"] or fnv1a(photo).lower() != metadata["fnv1a"].lower():
        raise ValueError("Photo length/checksum mismatch")
    if not photo.startswith(b"\xff\xd8") or not photo.endswith(b"\xff\xd9"):
        raise ValueError("Incomplete JPEG")
    metadata_text = json.dumps(metadata, indent=2, allow_nan=False) + "\n"
    stem = f"frame-{metadata['frame']:06d}-{metadata['state'].lower()}"
    name, copy = stem, 1
    while any((root / (name + suffix)).exists() for suffix in (".jpg", ".json", ".jpg.part", ".json.part")):
        copy += 1
        name = f"{stem}-copy-{copy:03d}"
    jpeg_part, json_part = root / (name + ".jpg.part"), root / (name + ".json.part")
    with jpeg_part.open("xb") as stream:
        stream.write(photo)
    with json_part.open("x", encoding="utf-8") as stream:
        stream.write(metadata_text)
    jpeg_part.replace(root / (name + ".jpg"))
    json_part.replace(root / (name + ".json"))
    return name


class Receiver:
    """Byte-preserving receiver; construct in an existing new session directory."""
    def __init__(self, root, label="test", *, clock=time.monotonic, now=utc_now):
        self.root, self.label, self.clock, self.now = Path(root), label, clock, now
        self.started = clock()
        self.raw = (self.root / "serial.raw").open("xb")
        try:
            self.events = (self.root / "events.jsonl").open("x", encoding="utf-8")
        except BaseException:
            self.raw.close()
            raise
        self.sequence = self.offset = self.received_bytes = 0
        self.buffer = bytearray()
        self.discard_line = False
        self.pending, self.parts, self.encoded_length = None, [], 0
        self.photos, self.last_motion = [], {}
        self.orphan_photo = False
        self.closed = False

    def emit(self, row, span=None):
        self.sequence += 1
        item = dict(row)
        item["_host"] = {"sequence": self.sequence, "received_utc": self.now(),
                         "elapsed_s": round(self.clock() - self.started, 6),
                         "raw_start": span[0] if span else None, "raw_end": span[1] if span else None}
        self.events.write(json.dumps(item, allow_nan=False) + "\n")
        self.events.flush()
        return item

    def error(self, code, detail, span=None):
        return self.emit({"recorder_event": "ERROR", "code": code, "detail": detail}, span)

    def command_sent(self, command):
        self.emit({"recorder_event": "HOST_COMMAND", "command": command,
                   "meaning": "completed host write; device acknowledgment is separate"})

    def clear_pending(self):
        self.pending, self.parts, self.encoded_length = None, [], 0

    def feed(self, data):
        if self.closed:
            raise ValueError("Receiver is closed")
        self.raw.write(data)
        self.raw.flush()
        self.received_bytes += len(data)
        self.buffer.extend(data)
        while b"\n" in self.buffer:
            raw, _, remaining = self.buffer.partition(b"\n")
            self.buffer = bytearray(remaining)
            span = self.offset, self.offset + len(raw) + 1
            self.offset = span[1]
            if self.discard_line:
                self.discard_line = False
                continue
            if len(raw) > MAX_SERIAL_LINE:
                self.error("serial_line_too_long", "Oversized line retained in serial.raw but not parsed", span)
                self.clear_pending()
                continue
            self.process_line(bytes(raw), span)
        if len(self.buffer) > MAX_SERIAL_LINE:
            span = self.offset, self.offset + len(self.buffer)
            if not self.discard_line:
                self.error("serial_line_too_long", "Unterminated oversized line retained; parsing resumes after its newline", span)
            self.offset = span[1]
            self.buffer.clear()
            self.clear_pending()
            self.discard_line = True

    def process_line(self, raw, span):
        try:
            original = raw.decode("utf-8").rstrip("\r")
        except UnicodeDecodeError:
            self.error("invalid_utf8", "Undecodable line retained exactly in serial.raw", span)
            return
        line = original.strip()
        if not line:
            return
        if line.startswith("PHOTO_BEGIN "):
            if self.pending is not None:
                self.error("photo_interrupted", "A new PHOTO_BEGIN interrupted the preceding transfer", span)
            self.clear_pending()
            self.orphan_photo = False
            try:
                candidate = strict_json(line[12:])
                validate_photo_metadata(candidate)
                self.pending = candidate
                self.emit({"recorder_event": "PHOTO_BEGIN", "frame": candidate["frame"], "metadata": candidate}, span)
            except (ValueError, TypeError, KeyError) as exc:
                self.error("invalid_photo_header", str(exc), span)
            return
        if line.startswith("PHOTO_DATA "):
            if self.pending is None:
                if not self.orphan_photo:
                    self.emit({"recorder_event": "PHOTO_FRAGMENT", "detail": "Data without a retained PHOTO_BEGIN; possibly attached mid-transfer"}, span)
                    self.orphan_photo = True
            else:
                part = line[11:]
                self.parts.append(part)
                self.encoded_length += len(part)
                if self.encoded_length > MAX_ENCODED_PHOTO:
                    self.error("photo_oversized", "Encoded photo transfer exceeded its bound", span)
                    self.clear_pending()
            return
        if line.startswith("PHOTO_END "):
            if self.pending is None:
                self.emit({"recorder_event": "PHOTO_FRAGMENT", "detail": "PHOTO_END without a retained complete transfer"}, span)
            else:
                try:
                    metadata = self.pending
                    matching = self.last_motion.get(metadata["frame"])
                    sequence = matching["_host"]["sequence"] if matching and device_metadata(matching) == metadata else None
                    info = dict(metadata, host_received=self.now(), test_label=self.label,
                                record_schema=SCHEMA_VERSION, motion_event_sequence=sequence)
                    name = save_photo(self.root, info, self.parts, line[10:])
                    self.photos.append((name, info))
                    self.emit({"recorder_event": "PHOTO_SAVED", "metadata_file": name + ".json", "image_file": name + ".jpg",
                               "motion_event_sequence": sequence}, span)
                except (ValueError, TypeError, KeyError) as exc:
                    self.error("photo_rejected", str(exc), span)
            self.clear_pending()
            self.orphan_photo = False
            return
        if line.startswith("MOTION "):
            try:
                metadata = strict_json(line[7:])
                validate_frame(metadata)
                stored = self.emit(metadata, span)
                self.last_motion[metadata["frame"]] = stored
            except (ValueError, TypeError, KeyError) as exc:
                self.error("invalid_motion", str(exc), span)
            return
        self.emit({"device_message": original}, span)
        if line == "BOOT" or line.startswith("BOOT "):
            if self.pending is not None:
                self.error("photo_interrupted_by_boot", "BOOT interrupted a photo transfer", span)
            self.clear_pending()
            self.last_motion.clear()

    def finish(self, reason="duration_limit"):
        if self.closed:
            return
        try:
            if self.pending is not None:
                self.error("photo_incomplete", "Final photo transfer incomplete; no successful image pair was recorded")
                self.clear_pending()
            if self.buffer or self.discard_line:
                self.emit({"recorder_event": "TRAILING_FRAGMENT", "bytes": len(self.buffer),
                           "detail": "Unterminated serial bytes remain in serial.raw"},
                          (self.offset, self.offset + len(self.buffer)))
            self.emit({"recorder_event": "RECORDING_END", "reason": reason})
        finally:
            self.raw.close()
            self.events.close()
            self.closed = True


def write_gallery(root, analysis):
    """Show only saved image bytes and observed selected/auxiliary metadata."""
    root = Path(root)
    frames = {frame["line"]: frame for frame in analysis["frames"]}
    cards = []
    for photo in analysis["photos"]:
        if not photo["checksum_verified"]:
            continue
        info = photo["metadata"]
        matching = photo["matching_event_lines"]
        frame = frames.get(matching[0]) if len(matching) == 1 else None
        scores = frame["scores"] if frame else None
        geometry, overlay = photo_geometry(info), ""
        geometry_note = {
            "not_reported": "Selected-region geometry not reported; no box is drawn.",
            "empty": "Recorded selected region has zero width or height; no box is drawn.",
            "invalid": "Selected-region geometry is invalid; original metadata is retained and no box is drawn.",
        }.get(geometry["status"], "")
        if geometry["status"] == "valid":
            left, top, width, height = geometry["percent_bounds"]
            overlay = (f'<div class="box" style="left:{left}%;top:{top}%;'
                       f'width:{width}%;height:{height}%"></div>')
        kind = frame["kind"] if frame else "unpaired photo"
        if info["state"] in {"SETTLING", "CALIBRATING", "CAMERA_TEST"}:
            selected = "Setup/diagnostic placeholder; not an operational detector area."
        else:
            area, cutoff = info.get("area_percent"), info.get("cutoff_percent")
            cutoff_text = f"{cutoff}%" if cutoff is not None else "not reported"
            selected = f"Selected region: {area}% area; recorded cutoff: {cutoff_text}." if area is not None else "Selected area not reported."
        if scores:
            score_text = (f"Reported grayscale: {scores['grayscale_percent']:.3f}% (cutoff {scores['grayscale_cutoff']:g}%); "
                          f"reported assisted union: {scores['assisted_percent']:.3f}% (cutoff {scores['color_cutoff']:g}%); "
                          f"color_enabled={int(scores['color_enabled'])}.")
        else:
            score_text = "Auxiliary scores unavailable or not uniquely associated; selected photo metadata is retained."
        alarm_text = (f"Software alarm-start event line(s): {frame['alarm_start_lines']}." if frame and frame["alarm_start_lines"] else "")
        name = html.escape(photo["image_file"], quote=True)
        metadata_name = html.escape(photo["metadata_file"], quote=True)
        cards.append(f'<article><h2>Frame {info["frame"]}: {html.escape(info["state"])}</h2>'
                     f'<div class="image"><img loading="lazy" alt="Recorded frame {info["frame"]}" src="{name}">{overlay}</div>'
                     f'<p>{html.escape(kind)}. {html.escape(selected)}</p><p>{html.escape(geometry_note)}</p>'
                     f'<p>{html.escape(score_text)}</p><p>{html.escape(alarm_text)}</p>'
                     f'<a href="{name}">Original JPEG</a> · <a href="{metadata_name}">Selected metadata</a></article>')
    counts = analysis["counts"]
    issues = analysis["errors"] + analysis["warnings"] + analysis["reference_warnings"]
    issue_list = "".join(f'<li>{html.escape(item["code"])}: {html.escape(str(item["detail"]))}</li>' for item in issues)
    page = (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Recorded detector evidence</title><style>body{{font:16px/1.5 system-ui;margin:24px;color:#18252c}}'
            f'main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}}article{{border:1px solid #ccd;padding:12px}}'
            f'.image{{position:relative;line-height:0}}img{{width:100%;height:auto}}.box{{position:absolute;border:2px solid #b45309;box-sizing:border-box}}'
            f'h2{{font-size:18px}}</style><h1>Recorded detector evidence</h1>'
            f'<p>{counts["verified_photos"]} verified photos; {counts["motion_frame_records"]} observed MOTION records; '
            f'{counts["camera_bursts"]} observed camera-burst records; {counts["unresolved_waits"]} unresolved PIR waits.</p>'
            '<p>Images are unchanged. Each box is the selected region supplied by the device, not an animal-recognition box or a separate assisted-region box. '
            'Assisted scores describe the grayscale/chroma union reported by the producer. Software alarm messages do not verify physical sound or light. '
            'Counts are observations, not independent accuracy trials.</p><p>Only received settings are displayed. Local source/binary hashes do not establish the running firmware identity.</p>'
            '<p><a href="events.jsonl">Events</a> · <a href="summary.json">Summary</a> · <a href="run_manifest.json">Manifest</a></p>'
            + ('<h2>Evidence limitations and errors</h2><ul>' + issue_list + '</ul>' if issues else '')
            + '<main>' + ''.join(cards) + '</main></html>\n')
    (root / "index.html").write_text(page, encoding="utf-8")


def source_snapshot():
    paths = [TOOLS / "record_photos.py", TOOLS / "recording.py", TOOLS / "requirements.txt",
             REPOSITORY / "firmware/motion-size/src/app_main.cpp", REPOSITORY / "firmware/motion-size/platformio.ini"]
    return [{"path": str(path.relative_to(REPOSITORY)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in paths if path.is_file()]


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--label", default="test")
    parser.add_argument("--output", type=Path, help="New session directory; must not exist")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--calibrate", action="store_true", help="Send BASELINE; clear the view before using")
    actions.add_argument("--arm", action="store_true", help="Send the existing ARM request for a controlled observation")
    parser.add_argument("--notes", default="", help="Operator-provided setup context")
    parser.add_argument("--config-file", type=Path, help="Hash a supplied file; does not apply configuration")
    parser.add_argument("--firmware-binary", type=Path, help="Hash a supplied binary; does not verify it was flashed")
    args = parser.parse_args(argv)
    if not 0 < args.seconds <= 3600:
        parser.error("--seconds must be greater than zero and at most 3600")
    for path in (args.config_file, args.firmware_binary):
        if path and not path.is_file():
            parser.error(f"File does not exist: {path}")
    try:
        import serial
    except ImportError:
        parser.error("pyserial is required for live recording; see tools/requirements.txt")
    label = re.sub(r"[^a-zA-Z0-9_-]", "-", args.label)[:60] or "test"
    root = (args.output or TOOLS / "captures" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + label)).resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"Output already exists; choose a new directory: {root}")
    except OSError as exc:
        print(f"Cannot create recording directory: {exc}", file=sys.stderr)
        return 1
    command = "BASELINE" if args.calibrate else "ARM" if args.arm else None
    manifest_path = root / "run_manifest.json"
    manifest = {"schema_version": SCHEMA_VERSION, "label": label, "operator_notes": args.notes,
                "started_utc": utc_now(), "closed": False, "artifacts": [],
                "recorder_configuration": {"port": args.port, "baudrate": 115200, "requested_seconds": args.seconds,
                                           "requested_command": command, "photo_grace_seconds": 5},
                "flashed_binary_identity": {"verified": False, "note": "Local source or supplied binary hashes do not verify the running device."}}
    receiver, connection, analysis = None, None, None
    reason, interrupted, finalization_failed = "duration_limit", False, False
    print(f"Recording to {root}", flush=True)
    try:
        manifest["local_source_snapshot"] = source_snapshot()
        manifest["supplied_file_hashes"] = {
            kind: {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for kind, path in (("configuration", args.config_file), ("firmware_binary", args.firmware_binary)) if path}
        _write_json(manifest_path, manifest)
        receiver = Receiver(root, label)
        connection = serial.Serial()
        connection.port, connection.baudrate, connection.timeout = args.port, 115200, 0.2
        connection.dtr = connection.rts = False
        connection.open()
        # Do not clear the input buffer or discard a first line.
        if command:
            payload = (command + "\n").encode("ascii")
            if connection.write(payload) != len(payload):
                raise OSError("Incomplete command write; no completed HOST_COMMAND recorded")
            receiver.command_sent(command)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline or (receiver.pending is not None and time.monotonic() < deadline + 5):
            receiver.feed(connection.read(8192))
    except KeyboardInterrupt:
        reason, interrupted = "operator_interrupt", True
    except (serial.SerialException, OSError, ValueError) as exc:
        reason = "io_error"
        if receiver and not receiver.closed:
            try:
                receiver.error("recording_io_error", str(exc))
            except OSError:
                finalization_failed = True
        print(f"Recording error: {exc}", file=sys.stderr)
    except Exception as exc:
        # Unexpected programming/runtime failures remain visible to callers.
        # Finalize what can be retained, but never describe this as a normal
        # duration-limit stop with an empty error list.
        reason = "unexpected_error"
        manifest["unexpected_error"] = {"type": type(exc).__name__, "message": str(exc)}
        if receiver and not receiver.closed:
            try:
                receiver.error("unexpected_error", f"{type(exc).__name__}: {exc}")
            except Exception as recording_exc:
                finalization_failed = True
                print(f"Could not record unexpected failure: {recording_exc}", file=sys.stderr)
        print(f"Unexpected recording failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
    finally:
        if connection is not None:
            try:
                connection.close()
            except (serial.SerialException, OSError) as exc:
                reason = "io_error"
                if receiver and not receiver.closed:
                    try:
                        receiver.error("serial_close_error", str(exc))
                    except OSError:
                        finalization_failed = True
        try:
            if receiver is None:
                finalization_failed = True
            else:
                if not receiver.received_bytes:
                    receiver.error("no_serial_data", "No serial bytes were received")
                receiver.finish(reason)
                analysis = analyze_session(root, read_saved_summary=False, verify_manifest=False)
                summary = summary_from_analysis(analysis, label) | {"recording_end_reason": reason}
                _write_json(root / "summary.json", summary)
                write_gallery(root, analysis)
                if not finalization_failed:
                    manifest.update(closed=True, ended_utc=utc_now(), end_reason=reason,
                                    observed_identity_messages=analysis["provenance"]["observed_identity_messages"],
                                    artifacts=[{"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                                               for path in sorted(root.iterdir()) if path.is_file() and path != manifest_path])
                    _write_json(manifest_path, manifest)
                print(json.dumps(summary, indent=2), flush=True)
                print(f"Gallery: {root / 'index.html'}", flush=True)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            finalization_failed = True
            print(f"Recording finalization failed; preserve partial files: {exc}", file=sys.stderr)
            if receiver and not receiver.closed:
                receiver.raw.close()
                receiver.events.close()
                receiver.closed = True
    if interrupted:
        return 130
    return 1 if finalization_failed or reason == "io_error" or analysis is None or analysis["errors"] or analysis["application_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
