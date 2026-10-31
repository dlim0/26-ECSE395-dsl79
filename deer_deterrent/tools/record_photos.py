"""Receive motion measurements and checksum-verified JPEG photos over USB."""
import argparse
import base64
import html
import json
import re
import time
from datetime import datetime
from pathlib import Path
import serial


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08x}'


def save_photo(root, metadata, encoded, ending):
    if str(metadata['frame']) != ending.strip():
        raise ValueError('Photo frame number mismatch')
    photo = base64.b64decode(''.join(encoded), validate=True)
    if len(photo) != metadata['jpeg_bytes'] or fnv1a(photo) != metadata['fnv1a']:
        raise ValueError('Photo length/checksum mismatch')
    if not (photo.startswith(b'\xff\xd8') and photo.endswith(b'\xff\xd9')):
        raise ValueError('Incomplete JPEG')
    name = f"frame-{metadata['frame']:06d}-{metadata['state'].lower()}"
    (root / f'{name}.jpg').write_bytes(photo)
    (root / f'{name}.json').write_text(json.dumps(metadata, indent=2))
    return name


def write_gallery(root, photos):
    cards = []
    for name, info in photos:
        x,y,w,h = info['bbox']
        box = f'left:{x/80*100}%;top:{y/60*100}%;width:{w/80*100}%;height:{h/60*100}%;'
        border = 'red' if info['state'] == 'LARGE_CHANGE' else 'orange'
        overlay = f'<div class="box" style="{box}border-color:{border}"></div>' if w and h else ''
        cards.append(f'<article><div class="image"><img src="{name}.jpg">{overlay}</div><p>Frame {info["frame"]}: {html.escape(info["state"])} | {info["area_percent"]:.3f}% changed area</p><a href="{name}.jpg">Original JPEG</a> · <a href="{name}.json">Measurements</a></article>')
    page = '<!doctype html><meta charset="utf-8"><title>Motion-size test photos</title><style>body{font-family:system-ui;margin:24px;background:#f3f4f6}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;padding:12px}.image{position:relative;line-height:0}img{width:100%;height:auto}.box{position:absolute;border:2px solid;box-sizing:border-box}</style><h1>Motion-size test photos</h1><p>Original photos are unchanged. Boxes show the largest changed region against the learned empty scene. Area cutoff is recorded with each photo; confirmation: 3 frames. This is not deer recognition.</p><main>' + ''.join(cards) + '</main>'
    (root/'index.html').write_text(page, encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='COM5')
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--label', default='test')
    p.add_argument('--calibrate', action='store_true', help='Request a new empty-scene reference; clear the view first.')
    p.add_argument('--arm', action='store_true', help='Clear the cooldown for a controlled test; requires PIR LOW then HIGH.')
    args = p.parse_args()
    if args.seconds <= 0 or args.seconds > 3600:
        p.error('--seconds must be between 0 and 3600')
    label = re.sub(r'[^a-zA-Z0-9_-]', '-', args.label)[:60] or 'test'
    root = Path(__file__).resolve().parent/'captures'/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+label)
    root.mkdir(parents=True)
    conn = serial.Serial()
    conn.port=args.port;conn.baudrate=115200;conn.timeout=0.5
    conn.dtr=False;conn.rts=False
    conn.open()
    conn.reset_input_buffer()
    photos=[];pending=None;parts=[];buffer=bytearray();measurements=[];errors=[];device_events=[];synced=False
    print('Saving photos to '+str(root),flush=True)
    if args.calibrate:
        conn.write(b'BASELINE\n')
        print('Keep the camera view EMPTY for calibration (about 8 seconds).',flush=True)
    elif args.arm:
        conn.write(b'ARM\n')
        print('Cooldown cleared for testing. Wait for PIR LOW before moving target into view.',flush=True)
    deadline=time.monotonic()+args.seconds
    try:
        with (root/'events.jsonl').open('w',encoding='utf-8') as events:
            while time.monotonic()<deadline or (pending is not None and time.monotonic()<deadline+5):
                buffer.extend(conn.read(8192))
                while b'\n' in buffer:
                    raw,_,buffer=buffer.partition(b'\n')
                    if not synced:
                        synced=True  # First line may be a fragment from an ongoing USB transfer.
                        continue
                    line=raw.decode(errors='replace').strip()
                    if line.startswith('PHOTO_DATA '):
                        if pending:
                            parts.append(line[11:])
                            if sum(map(len,parts)) > 700000:
                                errors.append('Oversized photo transfer');pending=None;parts=[]
                        continue
                    if line.startswith('PHOTO_BEGIN '):
                        pending=None;parts=[]
                        try:
                            candidate=json.loads(line[12:])
                            if not 0 < candidate['jpeg_bytes'] <= 500000: raise ValueError('Invalid JPEG length')
                            pending=candidate
                        except (ValueError,KeyError,TypeError) as e: errors.append(str(e))
                        continue
                    if line.startswith('PHOTO_END '):
                        if pending:
                            try:
                                info=dict(pending,host_received=datetime.now().astimezone().isoformat(),test_label=label)
                                name=save_photo(root,info,parts,line[10:])
                                photos.append((name,info));write_gallery(root,photos)
                                print(f'Saved {name}.jpg | area={info["area_percent"]:.3f}%',flush=True)
                            except (ValueError,KeyError,TypeError) as e:
                                errors.append(str(e));print('Discarded photo: '+str(e),flush=True)
                        pending=None;parts=[]
                        continue
                    if line.startswith('MOTION '):
                        try:
                            item=json.loads(line[7:]);measurements.append(item)
                            events.write(json.dumps(item)+'\n');events.flush()
                        except ValueError: errors.append('Invalid motion metadata')
                    elif line:
                        device_events.append(line)
                        events.write(json.dumps({'device_message':line})+'\n');events.flush()
                        if line.startswith(('BOOT','READY','CALIBRATION','ERROR','MOTION_SELFTEST','STATUS','PIR_TRIGGER','ARMED','DETERRENT_','BURST_END','COOLDOWN')):
                            print(line,flush=True)
                            if line.startswith('BOOT'): pending=None;parts=[]
    except (KeyboardInterrupt, serial.SerialException) as e:
        errors.append(type(e).__name__+': '+str(e))
    finally:
        conn.close()
        if pending: errors.append('Final photo transfer incomplete; discarded')
        scored=[m for m in measurements if m['state'] not in ('SETTLING','CALIBRATING')]
        summary={'label':label,'photos_saved':len(photos),'measured_frames':len(scored),'max_area_percent':max((m['area_percent'] for m in scored),default=None),'large_frames':sum(m['state']=='LARGE_CHANGE' for m in scored),'pir_triggers':sum(e.startswith('PIR_TRIGGER') for e in device_events),'deterrent_on_events':sum(e.startswith('DETERRENT_ON') for e in device_events),'deterrent_off_events':sum(e.startswith('DETERRENT_OFF') for e in device_events),'last_status':next((e for e in reversed(device_events) if e.startswith('STATUS')),None),'device_errors':[e for e in device_events if e.startswith('ERROR')],'errors':errors}
        (root/'summary.json').write_text(json.dumps(summary,indent=2))
        write_gallery(root,photos)
        print(json.dumps(summary),flush=True)
        print('Gallery: '+str(root/'index.html'),flush=True)
    return 0 if (photos or device_events) and not errors and not summary['device_errors'] else 1

if __name__=='__main__':
    raise SystemExit(main())


