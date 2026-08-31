#!/usr/bin/env python3
"""
MySub native messaging host — bridges the Chrome extension to yt-dlp.
Chrome launches this process, sends one JSON message via stdin, reads
the reply from stdout, then the process exits.
"""
import sys, json, struct, subprocess, os

YTDLP        = '/opt/homebrew/bin/yt-dlp'
DOWNLOAD_DIR = os.path.expanduser('~/Downloads/MySub')

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

def main():
    msg = recv()
    if not msg:
        send({'status': 'error', 'error': 'no message received'})
        return

    action = msg.get('action')

    if action == 'ping':
        send({'status': 'ok', 'ytdlp_found': os.path.exists(YTDLP)})

    elif action == 'download':
        url = msg.get('url', '')
        if not url:
            send({'status': 'error', 'error': 'no url provided'})
            return
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        try:
            # Spawn yt-dlp detached — return immediately so Chrome doesn't time out
            subprocess.Popen(
                [
                    YTDLP,
                    '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    '--merge-output-format', 'mp4',
                    '-o', os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
                    url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,   # detach from Chrome's process group
            )
            send({'status': 'started', 'dir': DOWNLOAD_DIR})
        except Exception as e:
            send({'status': 'error', 'error': str(e)})

    else:
        send({'status': 'error', 'error': f'unknown action: {action}'})

if __name__ == '__main__':
    main()
