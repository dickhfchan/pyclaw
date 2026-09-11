#!/usr/bin/env python3
"""
MySub native messaging host — bridges the Chrome extension to yt-dlp.
Chrome launches this process, sends one JSON message via stdin, reads
the reply from stdout, then the process exits.
"""
import sys, json, struct, subprocess, os, glob, re, time, urllib.parse

YTDLP        = '/opt/homebrew/bin/yt-dlp'
DOWNLOAD_DIR = os.path.expanduser('~/Downloads/MySub')
LOG_FILE     = os.path.expanduser('~/Downloads/MySub/mysub.log')
QUEUE_PREFIX = os.path.expanduser('~/Downloads/MySub/mysub_queue')
PARALLEL     = 3  # concurrent yt-dlp workers for batch downloads

# Cache written by the uploader (which has full disk access) so Arc's sandboxed
# native messaging host can read status without touching ~/Downloads directly.
STATUS_CACHE_FILE = os.path.expanduser('~/Library/Application Support/MySub/status_cache.json')
CACHE_MAX_AGE     = 900  # 15 minutes — uploader polls every 10 min

YTDLP_FLAGS = [
    '-f', 'bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
    '--merge-output-format', 'mp4',
    '--ffmpeg-location', '/opt/homebrew/bin/ffmpeg',
    '-o', os.path.join(DOWNLOAD_DIR, '%(title)s - %(id)s.%(ext)s'),
    '--continue',                    # resume partial .part files
    '--no-overwrites',               # skip already-completed files
    '--match-filter', '!is_live',   # skip live streams (would download forever)
    '--retries', '3',
]

def recv():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    length = struct.unpack('<I', raw)[0]
    return json.loads(sys.stdin.buffer.read(length).decode('utf-8'))

def send(obj):
    data = json.dumps(obj).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)) + data)
    sys.stdout.buffer.flush()

def cleanup_stale(download_dir):
    # Remove orphaned numbered audio files left by repeated failed attempts (e.g. filename.f140-5.m4a)
    for f in glob.glob(os.path.join(download_dir, '*.f*-*.m4a')):
        try:
            os.remove(f)
        except OSError:
            pass
    # Note: .part files are NOT removed — yt-dlp resumes them with --continue

STATE_FILE = os.path.expanduser('~/Downloads/MySub/mysub_uploaded.json')

def uploaded_video_ids():
    """Return set of YouTube video IDs already uploaded (extracted from stored filenames)."""
    try:
        with open(STATE_FILE) as f:
            names = json.load(f)
        ids = set()
        for name in names:
            m = re.search(r' - ([A-Za-z0-9_-]{11})(?:\.[^.]+)?$', os.path.splitext(name)[0])
            if m:
                ids.add(m.group(1))
        return ids
    except Exception:
        return set()

def video_id_from_url(url):
    """Extract YouTube video ID from a watch URL."""
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return qs.get('v', [None])[0]
    except Exception:
        return None

def batch_running():
    result = subprocess.run(
        ['pgrep', '-f', QUEUE_PREFIX],
        capture_output=True
    )
    return result.returncode == 0

def spawn_yt_dlp(args, log):
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    subprocess.Popen(
        [YTDLP] + YTDLP_FLAGS + args,
        stdout=log, stderr=log, env=env,
        start_new_session=True,
    )

def _title_from_name(filename):
    m = re.match(r'^(.+) - [A-Za-z0-9_-]{11}\.', filename)
    return m.group(1).strip() if m else None

def _id_from_filename(filename):
    m = re.search(r' - ([A-Za-z0-9_-]{11})(?:\.[^.]+)?$', os.path.splitext(filename)[0])
    return m.group(1) if m else None

def read_status_from_cache():
    """Read pre-computed status from the cache file written by the uploader.

    Returns (statuses, titles, debug_info) if the cache is fresh, else None.
    Arc's sandbox cannot list ~/Downloads, but ~/Library/Application Support is accessible.
    """
    try:
        with open(STATUS_CACHE_FILE) as f:
            cache = json.load(f)
        age = time.time() - cache.get('written_at', 0)
        if age > CACHE_MAX_AGE:
            return None

        statuses = {}
        titles = {}

        for name in cache.get('uploaded', []):
            vid_id = _id_from_filename(name)
            if vid_id:
                statuses[vid_id] = {'dl': None, 'up': 'uploaded'}

        current = cache.get('current')
        if current:
            m = re.search(r' - ([A-Za-z0-9_-]{11})\.', current)
            if m and m.group(1) not in statuses:
                vid_id = m.group(1)
                statuses[vid_id] = {'dl': 'downloaded', 'up': 'uploading'}
                t = _title_from_name(current)
                if t: titles[vid_id] = t

        for name in cache.get('mp4s', []):
            m = re.search(r' - ([A-Za-z0-9_-]{11})\.mp4$', name)
            if m and m.group(1) not in statuses:
                vid_id = m.group(1)
                statuses[vid_id] = {'dl': 'downloaded', 'up': 'in_queue'}
                t = _title_from_name(name)
                if t: titles[vid_id] = t

        for name in cache.get('parts', []):
            m = re.search(r' - ([A-Za-z0-9_-]{11})\.', name)
            if m and m.group(1) not in statuses:
                vid_id = m.group(1)
                statuses[vid_id] = {'dl': 'downloading', 'up': None}
                clean = re.sub(r'\.part.*$', '', name)
                t = _title_from_name(clean)
                if t: titles[vid_id] = t

        for url in cache.get('queued_urls', []):
            vid_id = video_id_from_url(url)
            if vid_id and vid_id not in statuses:
                statuses[vid_id] = {'dl': 'in_queue', 'up': None}

        return statuses, titles, None
    except Exception:
        return None

def main():
    msg = recv()
    if not msg:
        send({'status': 'error', 'error': 'no message received'})
        return

    action = msg.get('action')

    if action == 'ping':
        send({'status': 'ok', 'ytdlp_found': os.path.exists(YTDLP)})

    elif action == 'download':
        # Single-URL download — used by the manual ↓ button in the popup
        url = msg.get('url', '')
        if not url:
            send({'status': 'error', 'error': 'no url provided'})
            return
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        try:
            log = open(LOG_FILE, 'a')
            spawn_yt_dlp([url], log)
            send({'status': 'started', 'dir': DOWNLOAD_DIR})
        except Exception as e:
            send({'status': 'error', 'error': str(e)})

    elif action == 'download_batch':
        # Batch download — used by auto-download. Splits into PARALLEL workers so
        # exactly PARALLEL videos download at any given time instead of all at once.
        urls = msg.get('urls', [])
        if not urls:
            send({'status': 'error', 'error': 'no urls provided'})
            return
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        if batch_running():
            # A previous batch is still in progress — don't mark these as downloaded
            # so they'll be retried on the next scrape.
            send({'status': 'already_running', 'queued': len(urls)})
            return

        cleanup_stale(DOWNLOAD_DIR)

        # Skip URLs already uploaded to avoid re-downloading and wasting disk space
        done_ids = uploaded_video_ids()

        # Build a lookup of url → metadata from the richer `videos` field if present
        video_meta = {v['url']: v for v in msg.get('videos', []) if v.get('url')}

        new_urls = [u for u in urls if video_id_from_url(u) not in done_ids]
        if not new_urls:
            send({'status': 'skipped', 'reason': 'all urls already uploaded'})
            return
        urls = new_urls

        # Write a sidecar .info.json for each video so the uploader can pass
        # channel name to WeTube without embedding it in the filename.
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        for url in urls:
            vid_id = video_id_from_url(url)
            meta = video_meta.get(url, {})
            if vid_id and meta:
                sidecar = os.path.join(DOWNLOAD_DIR, f'mysub_{vid_id}.info.json')
                try:
                    with open(sidecar, 'w') as f:
                        json.dump({'channelName': meta.get('channelName', ''),
                                   'channelUrl': meta.get('channelUrl', '')}, f)
                except Exception:
                    pass

        # Round-robin split: video 0→worker0, 1→worker1, 2→worker2, 3→worker0, ...
        groups = [[] for _ in range(PARALLEL)]
        for i, url in enumerate(urls):
            groups[i % PARALLEL].append(url)

        try:
            log = open(LOG_FILE, 'a')
            started = 0
            for i, group in enumerate(groups):
                if not group:
                    continue
                queue_file = f'{QUEUE_PREFIX}_{i}.txt'
                with open(queue_file, 'w') as f:
                    f.write('\n'.join(group) + '\n')
                spawn_yt_dlp(['--batch-file', queue_file], log)
                started += 1

            # Start the uploader daemon if it isn't already running
            uploader = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mysub_uploader.py')
            if os.path.exists(uploader):
                running = subprocess.run(['pgrep', '-f', 'mysub_uploader.py'], capture_output=True)
                if running.returncode != 0:
                    subprocess.Popen(
                        [sys.executable, uploader],
                        stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )

            send({'status': 'started', 'count': len(urls), 'workers': started, 'dir': DOWNLOAD_DIR, 'skipped': len(msg.get('urls', [])) - len(urls)})
        except Exception as e:
            send({'status': 'error', 'error': str(e)})

    elif action == 'get_status':
        # Try the cache first (accessible from Arc sandbox); fall back to direct scan.
        cache_result = read_status_from_cache()
        if cache_result:
            statuses, titles, _ = cache_result
        else:
            statuses = {}
            titles = {}

            for vid_id in uploaded_video_ids():
                statuses[vid_id] = {'dl': None, 'up': 'uploaded'}

            uploader_state_file = os.path.join(DOWNLOAD_DIR, 'mysub_uploader_state.json')
            try:
                with open(uploader_state_file) as f:
                    current_name = json.load(f).get('current')
                if current_name:
                    m = re.search(r' - ([A-Za-z0-9_-]{11})\.', current_name)
                    if m and m.group(1) not in statuses:
                        vid_id = m.group(1)
                        statuses[vid_id] = {'dl': 'downloaded', 'up': 'uploading'}
                        t = _title_from_name(current_name)
                        if t: titles[vid_id] = t
            except Exception:
                pass

            for path in glob.glob(os.path.join(DOWNLOAD_DIR, '*.mp4')):
                name = os.path.basename(path)
                if re.search(r'\.f\d+\.mp4$', name):
                    continue
                m = re.search(r' - ([A-Za-z0-9_-]{11})\.mp4$', name)
                if m and m.group(1) not in statuses:
                    vid_id = m.group(1)
                    statuses[vid_id] = {'dl': 'downloaded', 'up': 'in_queue'}
                    t = _title_from_name(name)
                    if t: titles[vid_id] = t

            for path in glob.glob(os.path.join(DOWNLOAD_DIR, '*.part')):
                name = os.path.basename(path)
                m = re.search(r' - ([A-Za-z0-9_-]{11})\.', name)
                if m and m.group(1) not in statuses:
                    vid_id = m.group(1)
                    statuses[vid_id] = {'dl': 'downloading', 'up': None}
                    t = _title_from_name(re.sub(r'\.part.*$', '', name))
                    if t: titles[vid_id] = t

            for queue_file in glob.glob(QUEUE_PREFIX + '_*.txt'):
                try:
                    with open(queue_file) as f:
                        for line in f:
                            url = line.strip()
                            if not url:
                                continue
                            vid_id = video_id_from_url(url)
                            if vid_id and vid_id not in statuses:
                                statuses[vid_id] = {'dl': 'in_queue', 'up': None}
                except Exception:
                    pass

        send({'status': 'ok', 'statuses': statuses, 'titles': titles})

    elif action == 'download_transcript':
        url = msg.get('url', '')
        if not url:
            send({'status': 'error', 'error': 'no url provided'})
            return
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        try:
            log = open(LOG_FILE, 'a')
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            subprocess.Popen(
                [YTDLP,
                 '--write-auto-subs', '--write-subs',
                 '--sub-langs', 'en,zh-Hans,zh-Hant',
                 '--skip-download',
                 '--no-overwrites',
                 '-o', os.path.join(DOWNLOAD_DIR, '%(title)s - %(id)s.%(ext)s'),
                 url],
                stdout=log, stderr=log, env=env,
                start_new_session=True,
            )
            send({'status': 'started', 'dir': DOWNLOAD_DIR})
        except Exception as e:
            send({'status': 'error', 'error': str(e)})

    else:
        send({'status': 'error', 'error': f'unknown action: {action}'})

if __name__ == '__main__':
    main()
