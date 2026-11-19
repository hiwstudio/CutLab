"""Import the first four scenes from a MixFix project as a CutLab study.

Run with apps/server/.venv/Scripts/python and pass a MixFix project directory
and a licensed music file. The source project is never modified.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/server'))
from cutlab.config import FFMPEG

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='MixFix project directory')
parser.add_argument('--music', type=Path, required=True, help='Licensed music file for the study')
args = parser.parse_args()
SOURCE = args.source.expanduser().resolve()
music = args.music.expanduser().resolve()
OUT = ROOT / 'data' / f'demo-mixfix-{SOURCE.name}'
for required in (SOURCE / 'timeline/timeline.json', SOURCE / 'voiceover/voice.mp3', SOURCE / 'timing/timing_map.json', music):
    if not required.is_file():
        raise FileNotFoundError(f'Required input was not found: {required}')
OUT.mkdir(parents=True, exist_ok=True)
CHECKPOINT = OUT / 'import-state.json'
state = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if CHECKPOINT.exists() else {'assets': {}}

def save():
    CHECKPOINT.write_text(json.dumps(state, indent=2), encoding='utf-8')

def api(path, body=None):
    req = Request('http://127.0.0.1:8787/api/v1/' + path,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(error.read().decode()) from error

def transcode(name, args):
    dest = OUT / name
    if not dest.exists():
        tmp = dest.with_name('partial-' + name)
        subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y',
                        *args, '-threads', '2', str(tmp)], check=True)
        tmp.replace(dest)
    return dest

def ingest(path):
    key = path.name
    if key not in state['assets']:
        state['assets'][key] = api(f'projects/{pid}/assets', {'path': str(path)})
        save()
    result = state['assets'][key]
    for _ in range(180):
        job = api('jobs/' + result['job_id'])
        if job['state'] == 'done':
            return result['asset_id']
        if job['state'] in ('failed', 'cancelled'):
            raise RuntimeError(job)
        time.sleep(2)
    raise TimeoutError(f'Ingest still running: {key}')

scenes = json.loads((SOURCE / 'timeline/timeline.json').read_text(encoding='utf-8'))['scenes'][:4]
if not scenes:
    raise ValueError('The MixFix timeline contains no scenes.')
bounds = [s['start_ms'] for s in scenes] + [scenes[-1]['end_ms']]
duration_ms = bounds[-1]
duration_s = duration_ms / 1000
titles = [s.get('title') or f'Scene {i + 1}' for i, s in enumerate(scenes)]
for scene in scenes:
    path = Path(scene['visual']['path'])
    if not path.is_absolute():
        path = SOURCE / path
    if not path.is_file():
        raise FileNotFoundError(path)

if 'project_id' not in state:
    state['project_id'] = api('projects', {'name': f'{SOURCE.name} · MixFix study', 'canvas': {'width': 1280, 'height': 720, 'fps': 30}})['id']
    save()
pid = state['project_id']
print('Project:', pid, flush=True)
if not state.get('assembled'):
    footage = []
    for i, scene in enumerate(scenes):
        print('Preparing scene', i + 1, flush=True)
        visual_path = Path(scene['visual']['path'])
        if not visual_path.is_absolute():
            visual_path = SOURCE / visual_path
        safe_title = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in titles[i]).strip('-')[:48]
        safe_title = safe_title or f'scene-{i+1}'
        path = transcode(f'{i+1:02d}-{safe_title}.mp4', [
            '-ss', str(scene['visual'].get('trim_in_ms', 0) / 1000), '-i', str(visual_path),
            '-an', '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=2',
            '-t', str((bounds[i+1] - bounds[i]) / 1000), '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p'])
        footage.append(ingest(path))
    voice = ingest(transcode('MixFix-narration.wav', ['-i', str(SOURCE / 'voiceover/voice.mp3'), '-t', str(duration_s), '-ar', '48000', '-c:a', 'pcm_s16le']))
    fade_out_start = max(duration_s - 3, 0)
    bed = ingest(transcode('Study-music.wav', ['-i', str(music), '-t', str(duration_s), '-af', f'afade=t=in:d=1,afade=t=out:st={fade_out_start}:d=3', '-ar', '48000', '-c:a', 'pcm_s16le']))
    ops = []
    for tid, kind, name, role in [('footage','video','Footage','footage'), ('voice','audio','Voiceover','voiceover'), ('music','audio','Music','music'), ('caps','caption','Captions','captions')]:
        ops.extend([{'op':'add_track','id':'trk_'+tid,'kind':kind}, {'op':'set_track','track':'trk_'+tid,'name':name,'role':role, **({'gain_db': -24 if tid == 'music' else 0} if kind != 'caption' else {})}])
    for i in range(len(scenes)):
        start, end = bounds[i:i+2]
        ops.extend([{'op':'add_scene','title':titles[i],'start_ms':start,'end_ms':end},
                    {'op':'add_clip','track':'trk_footage','asset':footage[i],'in_ms':0,'out_ms':end-start,'start_ms':start},
                    {'op':'add_clip','track':'trk_voice','asset':voice,'in_ms':start,'out_ms':end,'start_ms':start}])
    ops.append({'op':'add_clip','track':'trk_music','asset':bed,'in_ms':0,'out_ms':duration_ms,'start_ms':0})
    words = json.loads((SOURCE / 'timing/timing_map.json').read_text(encoding='utf-8'))['words']
    for start, end in zip(bounds, bounds[1:]):
        selected = [w for w in words if start <= w['start_ms'] < end]
        for j in range(0, len(selected), 6):
            group = selected[j:j+6]
            a, b = group[0]['start_ms'], min(end, group[-1]['end_ms'])
            if b > a:
                ops.append({'op':'add_caption','track':'trk_caps','text':' '.join(w['text'] for w in group),'start_ms':a,'end_ms':b})
    head = api(f'projects/{pid}')['head_rev']
    result = api(f'projects/{pid}/apply', {'base_rev':head,'ops':ops,'mode':'commit'})
    state['assembled'] = True
    save()
    (OUT / 'IMPORT-NOTES.md').write_text(
        f'MixFix study excerpt from {SOURCE.name}, covering the first four scenes. '
        'The source project and its review state were not modified. Verify and record '
        'the licenses and provenance for the supplied footage, narration, and music.\n',
        encoding='utf-8',
    )
print(f'Open http://127.0.0.1:3000/p/{pid}', flush=True)
