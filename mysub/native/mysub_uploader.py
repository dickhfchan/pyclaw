#!/usr/bin/env python3
"""
MySub background uploader — polls ~/Downloads/MySub for fully downloaded .mp4
files, uploads each to WeTube, then deletes the local copy to free disk space.

Config (create once): ~/Downloads/MySub/mysub_config.json
{
  "wetube_url": "https://your-wetube.vercel.app",
  "upload_key": "your-MYSUB_UPLOAD_KEY-value"
}
"""
import glob
import http.client
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")

DOWNLOAD_DIR      = os.path.expanduser('~/Downloads/MySub')
CONFIG_FILE       = os.path.join(DOWNLOAD_DIR, 'mysub_config.json')
STATE_FILE        = os.path.join(DOWNLOAD_DIR, 'mysub_uploaded.json')
TRANSCRIPT_STATE  = os.path.join(DOWNLOAD_DIR, 'mysub_transcripts.json')
UPLOADER_STATE    = os.path.join(DOWNLOAD_DIR, 'mysub_uploader_state.json')
LOG_FILE          = os.path.join(DOWNLOAD_DIR, 'uploader.log')
LOCK_FILE         = os.path.join(DOWNLOAD_DIR, 'uploader.lock')
QUEUE_PREFIX      = os.path.join(DOWNLOAD_DIR, 'mysub_queue')

# Status cache: written here (full filesystem access), read by native host (sandboxed)
STATUS_CACHE_DIR  = os.path.expanduser('~/Library/Application Support/MySub')
STATUS_CACHE_FILE = os.path.join(STATUS_CACHE_DIR, 'status_cache.json')
FFPROBE      = '/opt/homebrew/bin/ffprobe'
FFMPEG       = '/opt/homebrew/bin/ffmpeg'
STABLE_SECS  = 60    # file must be unmodified this long before upload
POLL_SECS    = 600   # check every 10 minutes


def log(msg):
    line = f"[uploader] {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except OSError:
        print(line, flush=True)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        if cfg.get('wetube_url') and cfg.get('upload_key'):
            return cfg
    except Exception:
        pass
    return None


def load_state():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_state(uploaded):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(sorted(uploaded), f)
    except Exception:
        pass


def load_transcript_state():
    try:
        with open(TRANSCRIPT_STATE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_transcript_state(uploaded):
    try:
        with open(TRANSCRIPT_STATE, 'w') as f:
            json.dump(sorted(uploaded), f)
    except Exception:
        pass


def set_current_upload(filename):
    """Write the currently-uploading filename to the state file (None to clear)."""
    try:
        with open(UPLOADER_STATE, 'w') as f:
            json.dump({'current': filename}, f)
    except Exception:
        pass
    write_status_cache()


def write_status_cache():
    """Write a snapshot of current state to ~/Library/Application Support/MySub/.

    Arc's sandboxed native messaging host cannot list ~/Downloads, but it CAN read
    ~/Library/Application Support. The extension reads from here for status chips.
    Written atomically via a temp file + rename to avoid torn reads.
    """
    try:
        os.makedirs(STATUS_CACHE_DIR, exist_ok=True)

        uploaded_names = []
        try:
            with open(STATE_FILE) as f:
                uploaded_names = json.load(f)
        except Exception:
            pass

        current_name = None
        try:
            with open(UPLOADER_STATE) as f:
                current_name = json.load(f).get('current')
        except Exception:
            pass

        mp4s = [os.path.basename(p) for p in glob.glob(os.path.join(DOWNLOAD_DIR, '*.mp4'))
                if not re.search(r'\.f\d+\.mp4$', os.path.basename(p))]

        parts = [os.path.basename(p) for p in glob.glob(os.path.join(DOWNLOAD_DIR, '*.part'))]

        queued_urls = []
        for qf in glob.glob(QUEUE_PREFIX + '_*.txt'):
            try:
                with open(qf) as f:
                    for line in f:
                        url = line.strip()
                        if url:
                            queued_urls.append(url)
            except Exception:
                pass

        cache = {
            'uploaded': uploaded_names,
            'current': current_name,
            'mp4s': mp4s,
            'parts': parts,
            'queued_urls': queued_urls,
            'written_at': time.time(),
        }

        tmp = STATUS_CACHE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(cache, f)
        os.replace(tmp, STATUS_CACHE_FILE)
    except Exception:
        pass


def sanitize_r2_folder(name, max_len=200):
    import re as _re
    name = _re.sub(r'[/\\#%?*|<>"\'`\x00-\x1f\x7f]', '', name)
    name = _re.sub(r'\.{2,}', '.', name)
    name = name.strip()
    return name[:max_len].rstrip()


def vtt_to_srt(vtt_text):
    """Convert WebVTT text to SRT format."""
    import re as _re
    lines = vtt_text.splitlines()
    result = []
    index = 1
    i = 0
    while i < len(lines) and '-->' not in lines[i]:
        i += 1
    while i < len(lines):
        line = lines[i].strip()
        if '-->' in line:
            ts = _re.sub(r'\s+(align|position|line|size|vertical):[^\s]+', '', line)
            ts = ts.replace('.', ',')
            result.append(str(index))
            result.append(ts)
            index += 1
            i += 1
            cue_lines = []
            while i < len(lines) and lines[i].strip():
                text = _re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', lines[i])
                text = _re.sub(r'<[^>]+>', '', text)
                if text.strip():
                    cue_lines.append(text.strip())
                i += 1
            result.extend(cue_lines)
            result.append('')
        else:
            i += 1
    return '\n'.join(result)


def _put_transcript(base_url, upload_key, stem, lang, fmt, data, content_type):
    try:
        presign = api_post(base_url, '/api/uploads/mysub-transcript-presign', upload_key, {
            'stem': stem,
            'lang': lang,
            'format': fmt,
        })
        put_url = presign.get('url')
        put_headers = presign.get('headers', {})
        if not put_url:
            log(f"bad presign for transcript {stem} {lang}.{fmt}")
            return False
        status = put_bytes(put_url, data, content_type, put_headers)
        if status not in (200, 204):
            log(f"transcript PUT HTTP {status} for {lang}.{fmt}")
            return False
        return True
    except Exception as e:
        log(f"transcript upload error {lang}.{fmt}: {e}")
        return False


def upload_transcript(path, cfg):
    """Upload a .vtt transcript (plus SRT conversion) to R2."""
    filename = os.path.basename(path)
    name_no_ext = os.path.splitext(filename)[0]        # e.g. "Title - abc123.en"
    fmt = os.path.splitext(filename)[1].lstrip('.')    # "vtt"
    lang = os.path.splitext(name_no_ext)[1].lstrip('.')  # "en"
    stem = os.path.splitext(name_no_ext)[0]            # "Title - abc123"

    if not lang or not stem:
        log(f"skip transcript '{filename}': cannot parse stem/lang")
        return False

    safe_stem = sanitize_r2_folder(stem)
    if not safe_stem:
        log(f"skip transcript '{filename}': stem sanitizes to empty")
        return False

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            vtt_text = f.read()
    except Exception as e:
        log(f"read error for transcript '{filename}': {e}")
        return False

    base_url = cfg['wetube_url'].rstrip('/')
    key = cfg['upload_key']

    ok_vtt = _put_transcript(base_url, key, safe_stem, lang, 'vtt',
                             vtt_text.encode('utf-8'), 'text/vtt')
    srt_text = vtt_to_srt(vtt_text)
    ok_srt = _put_transcript(base_url, key, safe_stem, lang, 'srt',
                             srt_text.encode('utf-8'), 'text/plain')

    if ok_vtt or ok_srt:
        log(f"transcript done '{filename}': vtt={ok_vtt} srt={ok_srt}")
        return True
    return False


def get_video_info(path):
    """Return (width, height, duration_seconds) from ffprobe, or (None, None, 0) on error."""
    try:
        result = subprocess.run(
            [FFPROBE, '-v', 'quiet', '-print_format', 'json',
             '-show_streams', '-show_format', path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        width = height = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                w = int(stream.get('width', 0))
                h = int(stream.get('height', 0))
                if w and h:
                    width, height = w, h
                    break
        duration = float(data.get('format', {}).get('duration', 0) or 0)
        return width, height, duration
    except Exception as e:
        log(f"ffprobe error: {e}")
    return None, None, 0


def fetch_youtube_thumbnail(video_id):
    """Fetch the original YouTube thumbnail for a video ID. Returns bytes or None."""
    for quality in ('maxresdefault', 'hqdefault'):
        url = f'https://i.ytimg.com/vi/{video_id}/{quality}.jpg'
        try:
            parsed = urllib.parse.urlparse(url)
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=15, context=_SSL_CTX)
            conn.request('GET', parsed.path)
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            if resp.status == 200 and data:
                return data
        except Exception:
            pass
    return None


def generate_thumbnail(src_path, duration):
    """Fallback: extract a thumbnail from src_path at 10% of duration. Returns bytes or None."""
    try:
        ss = max(0.0, duration * 0.1)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            thumb_path = f.name
        result = subprocess.run(
            [FFMPEG, '-y', '-ss', str(ss), '-i', src_path,
             '-frames:v', '1', '-q:v', '3', thumb_path],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            log(f"ffmpeg thumbnail error: {result.stderr[-500:].decode(errors='replace')}")
            return None
        with open(thumb_path, 'rb') as f:
            data = f.read()
        return data if data else None
    except Exception as e:
        log(f"thumbnail generation error: {e}")
        return None
    finally:
        try:
            os.unlink(thumb_path)
        except Exception:
            pass


def is_stable(path):
    """Return True only when the file is a completed, merged mp4 (no ongoing yt-dlp activity)."""
    try:
        import re as _re
        name = os.path.basename(path)
        # Skip format-specific intermediate streams (e.g. title.f137.mp4, title.f140.m4a)
        if _re.search(r'\.f\d+\.[^.]+$', name):
            return False
        stat = os.stat(path)
        if stat.st_size == 0:
            return False
        if time.time() - stat.st_mtime < STABLE_SECS:
            return False
        # Any .part file with the same base name means ffmpeg is still merging
        base = os.path.splitext(path)[0]
        if glob.glob(base + '*.part') or glob.glob(base + '.f*.mp4.part'):
            return False
        return True
    except OSError:
        return False


def api_post(base_url, endpoint, key, body):
    """POST JSON to a WeTube API endpoint using the pre-shared key."""
    parsed = urllib.parse.urlparse(base_url + endpoint)
    data = json.dumps(body).encode()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {key}',
        'Content-Length': str(len(data)),
    }
    if parsed.scheme == 'https':
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=30, context=_SSL_CTX)
    else:
        conn = http.client.HTTPConnection(parsed.netloc, timeout=30)
    conn.request('POST', parsed.path + ('?' + parsed.query if parsed.query else ''), data, headers)
    resp = conn.getresponse()
    body_bytes = resp.read()
    conn.close()
    if resp.status not in (200, 201):
        raise RuntimeError(f"HTTP {resp.status}: {body_bytes[:200].decode(errors='replace')}")
    return json.loads(body_bytes)


def put_bytes(url_str, data, content_type, extra_headers=None):
    """PUT raw bytes to a presigned URL (used for small thumbnail upload)."""
    parsed = urllib.parse.urlparse(url_str)
    headers = {
        'Content-Type': content_type,
        'Content-Length': str(len(data)),
        **(extra_headers or {}),
    }
    if parsed.scheme == 'https':
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=60, context=_SSL_CTX)
    else:
        conn = http.client.HTTPConnection(parsed.netloc, timeout=60)
    conn.request('PUT', parsed.path + ('?' + parsed.query if parsed.query else ''), data, headers)
    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    return status


def stream_put(url_str, file_path, extra_headers=None):
    """Stream a file to a presigned PUT URL in 8 MB chunks (no full-file memory load)."""
    parsed = urllib.parse.urlparse(url_str)
    size = os.path.getsize(file_path)
    headers = {
        'Content-Type': 'video/mp4',
        'Content-Length': str(size),
        **(extra_headers or {}),
    }
    if parsed.scheme == 'https':
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=600, context=_SSL_CTX)
    else:
        conn = http.client.HTTPConnection(parsed.netloc, timeout=600)

    path_qs = parsed.path + ('?' + parsed.query if parsed.query else '')
    conn.putrequest('PUT', path_qs)
    for k, v in headers.items():
        conn.putheader(k, v)
    conn.endheaders()

    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            conn.send(chunk)

    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    return status


def read_sidecar(path):
    """Read the .info.json sidecar written by the native host for this video, if any."""
    m = re.search(r' - ([A-Za-z0-9_-]{11})\.[^.]+$', os.path.basename(path))
    if not m:
        return {}
    sidecar = os.path.join(DOWNLOAD_DIR, f'mysub_{m.group(1)}.info.json')
    try:
        with open(sidecar) as f:
            return json.load(f)
    except Exception:
        return {}


def upload_file(path, cfg):
    title = os.path.splitext(os.path.basename(path))[0]
    size  = os.path.getsize(path)
    width, height, duration = get_video_info(path)
    if not width or not height:
        log(f"skip '{title}': could not detect dimensions")
        return False

    base_url = cfg['wetube_url'].rstrip('/')
    key      = cfg['upload_key']

    sidecar     = read_sidecar(path)
    channel_name = sidecar.get('channelName', '').strip()

    # 1 — get presigned PUT URLs from WeTube (source + thumb)
    try:
        presign_body = {
            'title':    title,
            'filename': os.path.basename(path),
            'size':     size,
            'width':    width,
            'height':   height,
        }
        if channel_name:
            presign_body['channelName'] = channel_name
        presign = api_post(base_url, '/api/uploads/mysub-presign', key, presign_body)
    except Exception as e:
        log(f"presign failed for '{title}': {e}")
        return False

    video_id    = presign.get('videoId')
    put_url     = presign.get('url')
    put_headers = presign.get('headers', {})
    thumb_url   = presign.get('thumbUrl')
    thumb_headers = presign.get('thumbHeaders', {})
    if not video_id or not put_url:
        log(f"bad presign response for '{title}': {presign}")
        return False

    log(f"uploading '{title}' ({size // 1_048_576} MB) → videoId={video_id}")

    # 2 — get thumbnail: try original YouTube image first, fall back to ffmpeg frame
    thumb_uploaded = False
    if thumb_url:
        import re as _re
        yt_id_match = _re.search(r' - ([A-Za-z0-9_-]{11})$', title)
        thumb_data = None
        if yt_id_match:
            thumb_data = fetch_youtube_thumbnail(yt_id_match.group(1))
            if thumb_data:
                log(f"thumbnail fetched from YouTube ({len(thumb_data)} bytes) for '{title}'")
        if not thumb_data and duration > 0:
            thumb_data = generate_thumbnail(path, duration)
            if thumb_data:
                log(f"thumbnail generated via ffmpeg ({len(thumb_data)} bytes) for '{title}'")
        if thumb_data:
            try:
                ts = put_bytes(thumb_url, thumb_data, 'image/jpeg', thumb_headers)
                if ts in (200, 204):
                    thumb_uploaded = True
                else:
                    log(f"thumbnail PUT failed HTTP {ts} for '{title}'")
            except Exception as e:
                log(f"thumbnail PUT error for '{title}': {e}")
        else:
            log(f"thumbnail skipped for '{title}'")

    # 3 — stream source video directly to R2
    try:
        status = stream_put(put_url, path, put_headers)
        if status not in (200, 204):
            log(f"PUT failed HTTP {status} for '{title}'")
            return False
    except Exception as e:
        log(f"PUT error for '{title}': {e}")
        return False

    # 4 — notify WeTube the upload is complete → triggers transcoding
    try:
        api_post(base_url, '/api/uploads/mysub-complete', key, {
            'videoId': video_id,
            'thumbUploaded': thumb_uploaded,
        })
    except Exception as e:
        log(f"complete call failed for '{title}': {e}")
        return False

    log(f"done '{title}' → {base_url}/watch/{video_id}")
    return True


def acquire_lock():
    """Return a lock file fd, or None if another instance is already running.

    Opens in 'a' mode so the file is never truncated before the flock, avoiding
    the race where two instances simultaneously wipe the PID and both acquire
    locks on different inodes.
    """
    import fcntl
    for _ in range(2):
        try:
            fd = open(LOCK_FILE, 'a')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We own the lock — overwrite the file with our PID
            fd.seek(0)
            fd.truncate()
            fd.write(str(os.getpid()))
            fd.flush()
            return fd
        except OSError:
            # Lock held — check if the owning PID is actually alive
            try:
                pid_text = open(LOCK_FILE).read().strip()
                pid = int(pid_text)
                os.kill(pid, 0)  # signal 0: just checks existence
                return None      # process is alive, bail out
            except (ValueError, OSError):
                # PID file unreadable or process is dead — remove stale lock
                try:
                    os.unlink(LOCK_FILE)
                except OSError:
                    pass
    return None


def main():
    lock = acquire_lock()
    if lock is None:
        log("another uploader instance is running — exiting")
        return
    log("uploader started")
    uploaded = load_state()
    transcripts_done = load_transcript_state()

    while True:
        cfg = load_config()
        if not cfg:
            log(f"config missing at {CONFIG_FILE} — add wetube_url and upload_key")
            time.sleep(POLL_SECS)
            continue

        for path in sorted(glob.glob(os.path.join(DOWNLOAD_DIR, '*.mp4'))):
            name = os.path.basename(path)
            if name in uploaded:
                continue
            if not is_stable(path):
                continue
            set_current_upload(name)
            success = upload_file(path, cfg)
            set_current_upload(None)
            if success:
                try:
                    os.remove(path)
                    log(f"deleted local copy: {name}")
                except OSError as e:
                    log(f"could not delete {name}: {e}")
                # Clean up sidecar
                m = re.search(r' - ([A-Za-z0-9_-]{11})\.[^.]+$', name)
                if m:
                    try:
                        os.remove(os.path.join(DOWNLOAD_DIR, f'mysub_{m.group(1)}.info.json'))
                    except OSError:
                        pass
                uploaded.add(name)
                save_state(uploaded)

        for path in sorted(glob.glob(os.path.join(DOWNLOAD_DIR, '*.*.vtt'))):
            name = os.path.basename(path)
            if name in transcripts_done:
                continue
            if not is_stable(path):
                continue
            if upload_transcript(path, cfg):
                transcripts_done.add(name)
                save_transcript_state(transcripts_done)

        write_status_cache()
        time.sleep(POLL_SECS)


if __name__ == '__main__':
    main()
