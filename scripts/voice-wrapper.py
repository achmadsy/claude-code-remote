#!/usr/bin/env python3
"""Voice dictation wrapper for ttyd terminal on iPhone.

Serves a page with the ttyd terminal in an iframe and a native text input
field at the bottom. Dictation works in the native input, then text is
injected into the tmux session via `tmux send-keys`.
"""

import os
import re
import subprocess
import shutil

from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

TMUX = shutil.which("tmux") or "/usr/bin/tmux"
TAILSCALE = shutil.which("tailscale") or "/usr/bin/tailscale"
BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1")
TTYD_PORT = int(os.environ.get("TTYD_PORT", "7681"))
WRAPPER_PORT = int(os.environ.get("WRAPPER_PORT", "7682"))
TMUX_SESSION = "claude"
UPLOAD_DIR = Path(
    os.environ.get(
        "UPLOAD_DIR",
        "/home/ubuntu/claude-code-remote/uploads",
    )
)
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MiB


app = FastAPI()


def get_tailscale_ip():
    result = subprocess.run(
        [TAILSCALE, "ip", "-4"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    ip = result.stdout.strip()
    if not ip:
        raise RuntimeError("Tailscale has no IPv4 address")
    return ip


class TextInput(BaseModel):
    text: str


class KeyInput(BaseModel):
    key: str


class ScrollInput(BaseModel):
    dir: str  # up | down
    lines: int = 3


@app.get("/", response_class=HTMLResponse)
async def index():
    ip = get_tailscale_ip()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Claude Code Remote</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            height: 100%;
            background: #1a1a1a;
            overflow: hidden;
            font-family: -apple-system, system-ui, sans-serif;
            touch-action: manipulation;
            overscroll-behavior: none;
            -webkit-text-size-adjust: 100%;
        }}
        .container {{
            display: flex;
            flex-direction: column;
            height: 100vh;
            height: 100dvh;
            overflow: hidden;
        }}
        .terminal-frame {{
            flex: 1;
            border: none;
            width: 100%;
            touch-action: none;
            overscroll-behavior: none;
            background: #1e1e1e;
        }}
        .quick-keys {{
            display: flex;
            gap: 4px;
            padding: 4px 6px;
            background: #252525;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .quick-keys button {{
            padding: 8px 14px;
            font-size: 14px;
            font-family: 'Menlo', monospace;
            border: 1px solid #555;
            border-radius: 4px;
            background: #333;
            color: #ccc;
            cursor: pointer;
            white-space: nowrap;
            flex-shrink: 0;
        }}
        .quick-keys button:active {{
            background: #555;
        }}
        .input-bar {{
            display: flex;
            gap: 6px;
            padding: 6px;
            background: #2d2d2d;
            border-top: 1px solid #444;
        }}
        .input-bar textarea {{
            flex: 1;
            padding: 10px 12px;
            font-size: 16px;
            border: 1px solid #555;
            border-radius: 8px;
            background: #1a1a1a;
            color: #fff;
            outline: none;
            resize: none;
            overflow-y: hidden;
            min-height: 42px;
            max-height: 100px;
            line-height: 1.4;
            font-family: -apple-system, system-ui, sans-serif;
        }}
        .input-bar textarea:focus {{
            border-color: #007aff;
        }}
        .input-bar button {{
            padding: 10px 18px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            background: #007aff;
            color: #fff;
            cursor: pointer;
            white-space: nowrap;
        }}
        .input-bar button:active {{
            background: #005bb5;
        }}
        .copy-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.85);
            z-index: 100;
            flex-direction: column;
            padding: 12px;
        }}
        .copy-overlay.active {{
            display: flex;
        }}
        .copy-overlay textarea {{
            flex: 1;
            background: #1a1a1a;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 8px;
            padding: 12px;
            font-family: Menlo, monospace;
            font-size: 14px;
            line-height: 1.4;
            resize: none;
            -webkit-user-select: text;
            user-select: text;
            -webkit-overflow-scrolling: touch;
            touch-action: pan-y;
            overscroll-behavior: contain;
        }}
        .copy-hint {{
            color: #888;
            font-size: 13px;
            text-align: center;
            padding: 6px;
        }}
        .copy-overlay .close-btn {{
            margin-top: 8px;
            padding: 12px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            background: #555;
            color: #fff;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="container">
        <iframe class="terminal-frame" src="/terminal/"></iframe>
        <div class="quick-keys">
            <button onclick="sendKey('Up')">&#9650;</button>
            <button onclick="sendKey('Down')">&#9660;</button>
            <button onclick="sendKey('Left')">&#9664;</button>
            <button onclick="sendKey('Right')">&#9654;</button>
            <button onclick="sendKey('Tab')">Tab</button>
            <button onclick="sendKey('S-Tab')">⇧Tab</button>
            <button onclick="sendKey('Escape')">Esc</button>
            <button onclick="sendKey('C-c')">Ctrl+C</button>
            <button onclick="sendKey('C-b')">Ctrl+B</button>
            <button onclick="sendKey('Enter')">Enter</button>
            <button onclick="sendKey('C-l')">Clear</button>
            <button onclick="scrollPane('up', 5)">&#9650;&#9650;</button>
            <button onclick="scrollPane('down', 5)">&#9660;&#9660;</button>
            <button onclick="newSession()">New</button>
            <button onclick="resumeSession()">Resume</button>
            <button onclick="copyPane()">Copy</button>
            <button id="photoBtn" onclick="document.getElementById('photoInput').click()">&#128247;</button>
            <input type="file" id="photoInput" accept="image/*" multiple style="display:none"
                   onchange="uploadPhoto(this)">
        </div>
        <div class="input-bar">
            <textarea id="cmd" rows="1"
                      placeholder="Dictate or type here..."
                      autocomplete="off"
                      autocorrect="on"
                      enterkeyhint="send"></textarea>
            <button onclick="sendText()">Send</button>
        </div>
    </div>
    <div class="copy-overlay" id="copyOverlay">
        <div class="copy-hint">Long-press to select, then Copy</div>
        <textarea id="copyText" readonly></textarea>
        <button class="close-btn" onclick="closeCopy()">Close</button>
    </div>
    <script>
        const input = document.getElementById('cmd');
        const UPLOAD_DIR = '{UPLOAD_DIR}/';

        // Auto-resize textarea as content grows
        input.addEventListener('input', () => {{
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 100) + 'px';
        }});

        // Enter sends, Shift+Enter adds newline
        input.addEventListener('keydown', (e) => {{
            if (e.key === 'Enter' && !e.shiftKey) {{
                e.preventDefault();
                sendText();
            }}
        }});

        async function sendText(override) {{
            let text = override || input.value.trim();
            if (!text) return;
            // Swap [filename] placeholders to real paths
            text = text.replace(/\[([^\]]+)\]/g, (match, name) => {{
                if (name.match(/\.(jpg|jpeg|png|gif|webp|heic)$/i)) {{
                    return UPLOAD_DIR + name;
                }}
                return match;
            }});

            try {{
                await fetch('/send', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text }})
                }});
                if (!override) {{
                    input.value = '';
                    input.style.height = 'auto';
                    input.focus();
                }}
            }} catch (err) {{
                console.error('Send failed:', err);
            }}
        }}

        async function sendKey(key) {{
            try {{
                await fetch('/key', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ key }})
                }});
            }} catch (err) {{
                console.error('Key send failed:', err);
            }}
        }}

        async function scrollPane(dir, lines) {{
            try {{
                await fetch('/scroll', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ dir: dir, lines: lines || 5 }})
                }});
            }} catch (err) {{
                console.error('Scroll failed:', err);
            }}
        }}

        async function copyPane() {{
            try {{
                const resp = await fetch('/copy');
                const data = await resp.json();
                const overlay = document.getElementById('copyOverlay');
                const textarea = document.getElementById('copyText');
                textarea.value = data.text;
                overlay.classList.add('active');
                // Scroll to bottom so most recent output is visible
                textarea.scrollTop = textarea.scrollHeight;
            }} catch (err) {{
                console.error('Copy failed:', err);
            }}
        }}

        async function newSession() {{
            // Exit current Claude session, then start a fresh one
            await sendText('/exit');
            setTimeout(() => sendText('claude'), 1500);
        }}

        async function resumeSession() {{
            // Exit current Claude session, then open resume picker
            await sendText('/exit');
            setTimeout(() => sendText('claude --resume'), 1500);
        }}

        function closeCopy() {{
            document.getElementById('copyOverlay').classList.remove('active');
            input.focus();
        }}

        function compressImage(file, maxWidth, quality) {{
            return new Promise((resolve) => {{
                // Skip compression for non-image files
                if (!file.type.startsWith('image/')) {{
                    resolve(file);
                    return;
                }}
                const img = new Image();
                img.onload = () => {{
                    URL.revokeObjectURL(img.src);
                    let w = img.width, h = img.height;
                    if (w > maxWidth) {{
                        h = Math.round(h * maxWidth / w);
                        w = maxWidth;
                    }}
                    const canvas = document.createElement('canvas');
                    canvas.width = w;
                    canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    canvas.toBlob((blob) => {{
                        const name = file.name.replace(/\\.[^.]+$/, '.jpg');
                        resolve(new File([blob], name, {{ type: 'image/jpeg' }}));
                    }}, 'image/jpeg', quality);
                }};
                img.src = URL.createObjectURL(file);
            }});
        }}

        async function uploadPhoto(fileInput) {{
            const files = Array.from(fileInput.files);
            if (!files.length) return;
            const btn = document.getElementById('photoBtn');
            const origText = btn.textContent;
            const origPlaceholder = input.placeholder;

            // Show counter on button + status in textarea placeholder
            const total = files.length;
            let done = 0;
            btn.textContent = '0/' + total;
            btn.disabled = true;
            input.placeholder = 'Compressing ' + total + ' photo' + (total > 1 ? 's' : '') + '...';

            try {{
                // Compress all photos first (resize to 1568px, 85% JPEG quality)
                const compressed = await Promise.all(files.map(f => compressImage(f, 1568, 0.85)));
                input.placeholder = 'Uploading ' + total + ' photo' + (total > 1 ? 's' : '') + '...';

                // Upload all photos in parallel, updating counter as each finishes
                const uploads = compressed.map(file => {{
                    const form = new FormData();
                    form.append('file', file);
                    return fetch('/upload', {{ method: 'POST', body: form }})
                        .then(r => r.json())
                        .then(data => {{
                            done++;
                            btn.textContent = done + '/' + total;
                            input.placeholder = 'Uploaded ' + done + '/' + total + '...';
                            return data;
                        }});
                }});
                const results = await Promise.all(uploads);

                // Show friendly names in textarea
                const tags = results.filter(r => r.name).map(r => '[' + r.name + ']');
                if (tags.length) {{
                    const prefix = input.value.trim();
                    input.value = (prefix ? prefix + '\\n' : '') + tags.join('\\n') + '\\n';
                    input.style.height = 'auto';
                    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
                    input.focus();
                }}
            }} catch (err) {{
                console.error('Upload failed:', err);
                input.placeholder = 'Upload failed. Try again.';
                setTimeout(() => {{ input.placeholder = origPlaceholder; }}, 3000);
            }} finally {{
                btn.textContent = origText;
                btn.disabled = false;
                input.placeholder = origPlaceholder;
                fileInput.value = '';
            }}
        }}

        // iOS/touch: map vertical swipes inside the ttyd iframe to scrollback.
        // The iframe is same-origin, so we can attach listeners to its document.
        const terminal = document.querySelector('.terminal-frame');
        let touchState = null;
        let touchHandlersAttached = false;

        function terminalDoc() {{
            try {{
                return terminal.contentDocument;
            }} catch (err) {{
                return null;
            }}
        }}

        function scrollTargets() {{
            const doc = terminalDoc();
            if (!doc) return null;
            const viewport =
                doc.querySelector('.xterm-viewport') ||
                doc.querySelector('.xterm-screen') ||
                doc.querySelector('.xterm') ||
                doc.body;
            if (!viewport) return null;
            const wheelTarget =
                doc.querySelector('.xterm') ||
                doc.querySelector('.xterm-viewport') ||
                viewport;
            return {{ viewport, wheelTarget }};
        }}

        function scrollTerminalBy(deltaY) {{
            if (!deltaY) return;
            // Clamp per-event delta: unclamped touch deltas fling too fast.
            deltaY = Math.max(-40, Math.min(40, deltaY));
            const targets = scrollTargets();
            if (!targets) return;
            const {{ viewport, wheelTarget }} = targets;

            // Real scrollable viewport: adjust scrollTop directly (no wheel, avoids 2x).
            if (typeof viewport.scrollTop === 'number') {{
                const before = viewport.scrollTop;
                viewport.scrollTop = before + deltaY;
                if (viewport.scrollTop !== before) return;
            }}

            // Virtual/transformed viewport: ask xterm via wheel.
            try {{
                wheelTarget.dispatchEvent(new WheelEvent('wheel', {{
                    deltaX: 0,
                    deltaY: deltaY,
                    deltaMode: 0,
                    bubbles: true,
                    cancelable: true,
                    view: terminal.contentWindow,
                }}));
            }} catch (err) {{
                // ignore
            }}
        }}

        function onTermTouchStart(e) {{
            if (e.touches.length !== 1) {{
                touchState = null;
                return;
            }}
            touchState = {{
                lastX: e.touches[0].clientX,
                lastY: e.touches[0].clientY,
                axis: null,
                tui: undefined,
                pending: 0,
            }};
        }}

        function onTermTouchMove(e) {{
            if (!touchState || e.touches.length !== 1) return;
            const x = e.touches[0].clientX;
            const y = e.touches[0].clientY;
            const dx = x - touchState.lastX;
            const dy = y - touchState.lastY;
            touchState.lastX = x;
            touchState.lastY = y;

            if (!touchState.axis) {{
                if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx)) {{
                    touchState.axis = 'y';
                }} else if (Math.abs(dx) > 8) {{
                    touchState.axis = 'x';
                }} else {{
                    return;
                }}
            }}

            if (touchState.axis !== 'y') return;

            // Mode is cached per session on the iframe element: shell vs
            // TUI decides scroll path. First-ever gesture fetches /mode.
            if (touchState.tui === undefined) {{
                touchState.tui = terminal.__paneTui;
                if (touchState.tui === undefined && !terminal.__modeFetch) {{
                    terminal.__modeFetch = true;
                    fetch('/mode').then(r => r.json()).then(d => {{
                        terminal.__paneTui = !!d.alternate;
                    }}).catch(() => {{
                        terminal.__paneTui = false;
                    }});
                }}
            }}

            // Plain shell: drive tmux copy-mode via /scroll so upper
            // history lines move. Wheel would leak into zsh as arrows
            // (history browse); xterm scrollTop has no tmux history.
            // TUI (alternate screen): wheel forwarding drives the app.
            e.preventDefault();
            if (touchState.tui === true) {{
                scrollTerminalBy(-dy);
            }} else if (touchState.tui === false) {{
                touchState.pending += -dy;
                const step = Math.max(-40, Math.min(40, touchState.pending));
                if (Math.abs(step) < 12) return;
                touchState.pending -= step;
                // Finger down (dy>0) → show older lines above → dir=up.
                const dir = step > 0 ? 'up' : 'down';
                const lines = Math.max(1, Math.min(8, Math.round(Math.abs(step) / 12)));
                fetch('/scroll', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ dir: dir, lines: lines }}),
                }}).catch(() => {{}});
            }}
            // tui unknown (fetch in flight): skip this gesture.
        }}

        function onTermTouchEnd(e) {{
            touchState = null;
        }}

        function attachTerminalTouchScroll() {{
            const doc = terminalDoc();
            if (!doc || !doc.documentElement) return;
            if (touchHandlersAttached && doc === attachTerminalTouchScroll._doc) return;

            const root = doc.documentElement;
            root.addEventListener('touchstart', onTermTouchStart, {{ passive: true }});
            root.addEventListener('touchmove', onTermTouchMove, {{ passive: false }});
            root.addEventListener('touchend', onTermTouchEnd, {{ passive: true }});
            root.addEventListener('touchcancel', onTermTouchEnd, {{ passive: true }});

            // Also cover the xterm node if it appears after first paint.
            const style = doc.createElement('style');
            style.textContent = `
                html, body, .xterm, .xterm-viewport, .xterm-screen {{
                    touch-action: none !important;
                    overscroll-behavior: none !important;
                    -webkit-overflow-scrolling: touch !important;
                }}
            `;
            doc.documentElement.appendChild(style);

            touchHandlersAttached = true;
            attachTerminalTouchScroll._doc = doc;
        }}

        function armTerminalTouchScroll() {{
            attachTerminalTouchScroll();
            // iframe may not be ready on first paint
            let tries = 0;
            const timer = setInterval(() => {{
                attachTerminalTouchScroll();
                tries += 1;
                if (touchHandlersAttached || tries > 40) clearInterval(timer);
            }}, 250);
        }}

        terminal.addEventListener('load', () => {{
            touchHandlersAttached = false;
            touchState = null;
            attachTerminalTouchScroll();
        }});

        // Auto-reconnect: reload iframe when tab becomes visible again
        document.addEventListener('visibilitychange', () => {{
            if (document.visibilityState === 'visible') {{
                terminal.src = terminal.src;
                armTerminalTouchScroll();
            }}
        }});

        function pollPaneMode() {{
            // Keep shell/TUI state fresh: alternate_on flips when claude
            // or vim starts/stops inside the pane.
            fetch('/mode').then(r => r.json()).then(d => {{
                terminal.__paneTui = !!d.alternate;
            }}).catch(() => {{}});
        }}
        setInterval(pollPaneMode, 3000);
        pollPaneMode();

        armTerminalTouchScroll();
        input.focus();
    </script>
</body>
</html>"""


@app.post("/send")
async def send_text(payload: TextInput):
    """Send literal text to tmux, then press Enter."""
    # Leave copy-mode first so text hits the prompt, not the selection.
    subprocess.run([TMUX, "send-keys", "-t", TMUX_SESSION, "Escape"], timeout=3)
    subprocess.run(
        [TMUX, "send-keys", "-t", TMUX_SESSION, "-l", payload.text],
        timeout=5,
    )
    subprocess.run(
        [TMUX, "send-keys", "-t", TMUX_SESSION, "Enter"],
        timeout=5,
    )
    return {"status": "sent"}


ALLOWED_KEYS = {
    "Up", "Down", "Left", "Right", "Tab", "S-Tab", "Escape", "Enter",
    "C-c", "C-b", "C-l", "C-d", "C-z", "C-a", "C-e", "C-k", "C-u",
    "BSpace", "DC", "Home", "End", "PPage", "NPage",
}


@app.post("/key")
async def send_key(payload: KeyInput):
    """Send a special key (Escape, C-c, Enter, etc.) to tmux."""
    if payload.key not in ALLOWED_KEYS:
        return {"status": "rejected", "error": "key not allowed"}
    subprocess.run(
        [TMUX, "send-keys", "-t", TMUX_SESSION, payload.key],
        timeout=5,
    )
    return {"status": "sent"}


@app.get("/mode")
async def term_mode():
    """Alternate-screen state: TUI (claude/vim) vs plain shell."""
    result = subprocess.run(
        [TMUX, "display-message", "-t", TMUX_SESSION, "-p", "#{alternate_on}"],
        capture_output=True, text=True, timeout=5,
    )
    return {"alternate": result.stdout.strip() == "1"}


@app.post("/scroll")
async def scroll_pane(payload: ScrollInput):
    """Scroll tmux history via copy-mode (xterm buffer has no upper lines)."""
    if payload.dir not in ("up", "down"):
        return {"status": "rejected", "error": "dir must be up or down"}
    lines = max(1, min(int(payload.lines), 50))
    try:
        # Enter copy-mode if not already there (no-op if already in it).
        subprocess.run([TMUX, "copy-mode", "-t", TMUX_SESSION], timeout=3)
        if payload.dir == "up":
            cmd = ["send-keys", "-t", TMUX_SESSION, "-X", f"scroll-up -N {lines}"]
        else:
            cmd = ["send-keys", "-t", TMUX_SESSION, "-X", f"scroll-down -N {lines}"]
        subprocess.run([TMUX] + cmd, timeout=3)
        return {"status": "scrolled", "dir": payload.dir, "lines": lines}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.get("/copy")
async def copy_pane():
    """Capture full tmux pane scrollback for copying."""
    result = subprocess.run(
        [TMUX, "capture-pane", "-t", TMUX_SESSION, "-p", "-S", "-"],
        capture_output=True, text=True, timeout=5,
    )
    return {"text": result.stdout}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save an uploaded file using its original name and return the path."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize filename: strip path components and special characters
    raw_name = file.filename or "photo.jpg"
    name = Path(raw_name).name
    name = re.sub(r'[^\w.\-]', '_', name)
    if not name or name.startswith('.'):
        name = "photo.jpg"
    dest = UPLOAD_DIR / name
    # Handle duplicate filenames with a counter suffix
    counter = 2
    while dest.exists():
        stem = Path(name).stem
        ext = Path(name).suffix
        dest = UPLOAD_DIR / f"{stem}-{counter}{ext}"
        counter += 1
    # Stream to disk and remove partial files when limit is exceeded.
    total = 0
    try:
        with dest.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE:
                    raise ValueError("File too large (max 20MB)")
                output.write(chunk)
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        return {"error": str(exc)}
    return {"name": dest.name, "path": str(dest)}


if __name__ == "__main__":
    print(f"Voice wrapper backend: http://{BIND_HOST}:{WRAPPER_PORT}")
    print(f"Terminal backend: http://{BIND_HOST}:{TTYD_PORT}/terminal/")
    uvicorn.run(app, host=BIND_HOST, port=WRAPPER_PORT)
