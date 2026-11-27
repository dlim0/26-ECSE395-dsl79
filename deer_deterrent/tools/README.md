# Detector recording

`record_photos.py` records the ground detector's serial messages and JPEG transfers. It keeps the received bytes, the device's selected-region measurements and the separately reported grayscale/assisted scores, then creates a summary and a local gallery. It does not run camera processing or decide whether to trigger an output.

Run the commands below from the `deer_deterrent` directory with Python 3.10 or newer. Install the existing serial dependency in the Python environment used for recording:

```sh
python -m pip install -r tools/requirements.txt
```

For a new recording, choose the board's actual serial port and a new output directory:

```sh
python tools/record_photos.py --port COM5 --seconds 60 --label outside-dark-inspection --output tools/captures/inspection-01
```

`COM5` is an example port and the default; choose the board's actual port. The recorder uses 115200 baud. Close other monitors using the selected port. The output directory must be new so that a recording cannot replace an earlier session. Without `--output`, the recorder creates a timestamped directory under `tools/captures/`, ending with the sanitized label.

| Option | Purpose |
|---|---|
| `--port` | Serial port to open. |
| `--seconds` | Recording duration in seconds: greater than zero and at most 3600; default 60. |
| `--label` | Label stored with the recording; default `test`. |
| `--output` | New directory for the session files. |
| `--notes` | Operator notes stored with the session. |
| `--calibrate` | Request the existing `BASELINE` command. |
| `--arm` | Request the existing `ARM` command. |
| `--config-file` | Hash a supplied local configuration file for provenance. |
| `--firmware-binary` | Hash a supplied local binary for provenance. |

`--calibrate` and `--arm` are mutually exclusive. Without either flag, the recorder sends neither command. A successful host write records a request; an observed device acknowledgment is a separate event. Hashing a configuration file or binary identifies that local file and does not establish what was running on the board.

## Saved evidence

| File | What it preserves |
|---|---|
| `serial.raw` | The bytes actually received, including malformed text, incomplete transfers and final fragments. |
| `events.jsonl` | Ordered device records/messages and host events, with receipt references and raw-byte spans where those bytes were captured. |
| Per-photo `.jpg` and `.json` | The transferred JPEG and its device metadata. Reserved host fields identify receipt/association information; they do not replace the device's selected region. Duplicate frame identities receive distinct names. |
| `summary.json` | Schema-3 counts, observed wait/capture history, software alarm events, association quality, diagnostics and provenance. |
| `index.html` | A gallery of retained photos with their selected-region measurements and separately associated score context. Open it locally with its session files. |
| `run_manifest.json` | Session provenance, close status and the paths, lengths and SHA-256 values of saved artifacts. |

Photo acceptance checks the transfer's frame identity, base64, declared byte length, FNV-1a checksum and JPEG start/end markers. It does not independently decode the JPEG. A failed or interrupted transfer remains visible in the raw stream and event record and is not reported as a successful photo. A complete manifest is written only after its artifacts are finalized; `.part` files or an open manifest identify incomplete finalization.

When a photo includes a region box and grid, the analyzer checks their shape, numeric values and bounds separately from JPEG integrity. Malformed or incomplete geometry is reported as an analysis error; the original verified JPEG and sidecar are kept, and the gallery omits the overlay. Absent geometry and valid empty regions do not create a box.

An auxiliary score row is associated with a measurement only when frame identity and the observed event history make the match unambiguous. Missing, duplicate, conflicting or malformed score context remains explicit without silently discarding an otherwise verified photo. An observed boot separates reused frame identities. The original score message remains in the event record, and analyzed outputs reference it rather than turning its fields into device-selected metadata.

## Reading current detector records

The current producer has separate vibration-wait and camera-capture stages. `PIR_TRIGGER waiting_for_vibration_s=...` opens a wait; `VIBRATION_RECEIVED starting_max_10_frames=1` starts capture; a vibration timeout can end a wait without taking a photo. A recording that starts at the receipt can contain a complete camera burst while lacking its preceding PIR history. A final unresolved wait is not a truncated camera burst, and elapsed host time does not supply a missing device timeout.

Attempt counts, measurement counts and photo counts are distinct. The current vibration producer can consume an attempt on a JPEG-decode error and continue the burst. The recorder keeps that error event without inventing the missing measurement, score or image. Interpretation of reported attempt counts is identified as interpretation against the reference producer contract, separately from transfer integrity and observed firmware identity.

`DETECTION_SCORES` reports grayscale area, assisted area, the enable flag and both cutoffs. The assisted value describes the grayscale mask combined with enabled chroma-range assistance; it is not a separate color-only measurement. When assistance is disabled, its reported zero is not a measurement of a computed absent-color region. The MOTION record contains the region actually selected by the producer. The gallery preserves that selected box/area/cutoff and displays the auxiliary percentages separately; it does not draw an invented second box or replace the selected area with the larger percentage.

SETTLING and CALIBRATING records remain setup evidence. CAMERA_TEST and LARGE_CHANGE_TEST_ONLY remain diagnostic evidence; a test-only qualification is not an operational alarm. Diagnostic classification does not erase a received attempt from an explicitly observed test-camera burst.

`DETERRENT_ON` and `DETERRENT_OFF` are software messages. ON may arrive before the matching frame; it remains an observed event and is associated later only when the match is unambiguous. An unpaired ON message does not create a measurement or prove physical sound/light. Likewise, a qualifying state without an ON message does not create an observed alarm-command count.

The summary distinguishes the last heartbeat from later events and recording-end context. Counts describe observed records and sequences, not independent accuracy trials. Unknown state/message variants remain available without being silently scored. A gallery does not assert a fixed confirmation-frame setting when that setting was not recorded.

## Provenance and incomplete observations

Observed BOOT, READY, mode and identity messages are retained when received. Missing calibration history, baseline images, mode or firmware identity remains unknown; a per-frame `color_enabled` value does not supply those missing facts. Local source/configuration hashes remain separate from observed board identity. Host receipt times are not exposure timestamps.

The analyzer can read retained event/sidecar/photo sessions that predate this recorder. If a session has no original `serial.raw`, analysis cannot provide original raw-byte offsets or reconstruct that missing stream. It also cannot derive the learned baseline from an apparently empty picture. Original captures, galleries and the dated handoff remain evidence; any newly generated output belongs in a separate destination.

Transfer corruption, malformed required metadata or supplied geometry, conflicting protocol records, serial failures and empty receipt are recording failures. Auxiliary-context gaps, unfinished waits/bursts and SDK diagnostics are reported separately. Application error messages remain visible even if later work completes. The command's successful exit means the recording closed without its defined errors; it does not mean detection succeeded or physical outputs were verified.

For an unexpected internal exception, the recorder marks an unexpected failure and attempts to finalize the available evidence, then re-raises the original exception so its traceback remains visible. It does not report that interrupted run as normal duration-limit completion. If finalization itself cannot finish, the available partial files and open manifest remain evidence of that incomplete result.

| Exit code | Meaning |
|---:|---|
| `0` | Recording and finalization completed without the defined recording errors. |
| `1` | A recording, integrity, application, I/O or finalization failure was reported. |
| `2` | Arguments or setup were invalid, or the serial dependency was unavailable. |
| `130` | The operator interrupted recording; the recorder attempted to finalize the evidence already received. |

## Tests

From `deer_deterrent`:

```sh
python -I -B -m unittest discover -s tools -p "test_*.py" -v
```

The current suite exercises transport integrity, interrupted and duplicate captures, score/alarm associations, wait/capture boundaries, decode-error accounting, diagnostic records, summary/gallery meaning, manifests and stand-in serial ports. Constructed streams are explicitly synthetic. The retained outside-dark session is read as event/sidecar/JPEG evidence; no original serial transcript or baseline image is fabricated.

The tests require no board, network service, model, Pillow or C++ compiler. They do not import the historical native growth replay, classifier/laptop clients or night-control code. Existing transfer tests are checks of transport bytes and metadata; their marker-delimited fixture is not an image-decoding test.
