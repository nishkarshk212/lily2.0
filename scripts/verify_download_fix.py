"""Standalone verification of the Lily download-pipeline fix (no deploy, no network).

Asserts:
  1. config.YT_API_BASE_URL always carries a scheme (InvalidUrlClientError guard).
  2. COOKIES_DATA (base64 Netscape) decodes to cookies/cookie_0.txt at startup.
  3. _railway_download now calls /download (JSON) not /play/audio (403).
  4. _local_ytdlp_download uses cookie-aware player_client + --extractor-args.
  5. _find_downloaded_file is extension-agnostic (no false "no output file").
"""
import os, sys, re, base64, asyncio, types, importlib.util
REPO = "/Users/nishkarshkumar/lily2.0"
PYLIB = os.path.join(REPO, "Lily")
sys.path.insert(0, REPO)

# Real env vars for the genuine config.py (simulates deploy .env, incl. schemeless URL bug)
os.environ["COOKIES_DATA"] = base64.b64encode(
    b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t9999999999\tTEST\tabc\n"
).decode()
os.environ["YT_API_BASE_URL"] = "youtube-api-music-production-824b.up.railway.app"  # schemeless -> must be fixed

# ── minimal stubs ──────────────────────────────────────────────────────────
lime = types.ModuleType("Lily"); lime.__path__ = [PYLIB]; lime.__package__ = "Lily"
sys.modules["Lily"] = lime

class _Filt:
    def __invert__(self): return self
    def __and__(self, o): return self
    def __or__(self, o): return self
class _Filters:
    def __getattr__(self, n):
        def fn(*a, **k): return _Filt()
        return fn
pyrogram = types.ModuleType("pyrogram"); pyrogram.filters = _Filters()
pyro_types = types.ModuleType("pyrogram.types")
for _n in ("Message", "CallbackQuery", "Chat", "User", "MessageEntity"):
    setattr(pyro_types, _n, object)
pyrogram.types = pyro_types
pyro_enums = types.ModuleType("pyrogram.enums")
for _n in ("MessageEntityType", "ChatType", "ParseMode", "ChatMemberStatus", "MessageServiceType"):
    setattr(pyro_enums, _n, object)
pyrogram.enums = pyro_enums
sys.modules["pyrogram"] = pyrogram
sys.modules["pyrogram.types"] = pyro_types
sys.modules["pyrogram.enums"] = pyro_enums

logger = types.ModuleType("Lily.logger")
logger.info = logger.warning = logger.error = lambda *a, **k: None
sys.modules["Lily.logger"] = logger

helpers = types.ModuleType("Lily.helpers")
class _Track:
    def __init__(self, id): self.id = id; self.file_path = None; self.stream_url = None
helpers.Track = helpers.Media = _Track
helpers.utils = types.SimpleNamespace(format_duration=lambda s: str(s), to_seconds=lambda s: 0)
sys.modules["Lily.helpers"] = helpers

for mod in ["app", "anon", "db", "lang", "queue", "tg", "xbit", "nexgen", "yt_api", "aruyt", "mongo", "callbacks"]:
    m = types.ModuleType("Lily." + mod); m.__getattr__ = lambda n: None; sys.modules["Lily." + mod] = m

# py_yt + yt_dlp stubs
py_yt = types.ModuleType("py_yt")
class _VideosSearch:
    def __init__(self, *a, **k): pass
    async def next(self): return {"result": []}
py_yt.VideosSearch = _VideosSearch
py_yt.Playlist = types.SimpleNamespace(get=lambda *a, **k: [])
sys.modules["py_yt"] = py_yt
yt_dlp = types.ModuleType("yt_dlp")
yt_dlp.YoutubeDL = object
sys.modules["yt_dlp"] = yt_dlp

# Load the REAL config.py as Lily.config (exercises _ensure_scheme + COOKIES_DATA wiring)
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m

# config.py imports dotenv/os only; safe to load standalone.
load("Lily.config", os.path.join(REPO, "config.py"))

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name); ok = ok and cond

yt = load("Lily.core.youtube", os.path.join(PYLIB, "core", "youtube.py"))

# 1. scheme normalisation — test the function directly (config reads env at runtime)
from Lily.config import _ensure_scheme
check("schemeless host gets https", _ensure_scheme("youtube-api-music-production-824b.up.railway.app").startswith("https://"))
check("already-https host untouched", _ensure_scheme("https://x.com").startswith("https://"))
check("empty url untouched", _ensure_scheme("") == "")

# 2. COOKIES_DATA decoded to cookie_0.txt (happens in YouTube.__init__)
y = yt.YouTube()
cookies_dir = y.cookies_dir
cf = os.path.join(cookies_dir, "cookie_0.txt")
check("cookie_0.txt created from COOKIES_DATA", os.path.exists(cf))
if os.path.exists(cf):
    check("cookie_0.txt is Netscape format", open(cf).read().startswith("# Netscape"))

# 3. railway downloader uses /download not /play/audio (exclude docstring mention)
src = open(os.path.join(PYLIB, "core", "youtube.py")).read()
check("railway calls /download endpoint", 'f"{base}/download"' in src)
# a real call to /play/audio would be f-stringed like the /download one; docstring only says "previously-used /play/audio"
play_audio_call = 'f"{base}/play/audio"' in src or 'f"{RAILWAY_YT_API_URL}/play/audio' in src
check("railway no longer CALLS /play/audio", not play_audio_call)

# 4. local ytdlp uses cookie-aware clients + extractor-args
check("local ytdlp sends --extractor-args player_client", "--extractor-args" in src)
check("local ytdlp uses tv_downgraded/web_safari", "tv_downgraded" in src and "web_safari" in src)
check("local ytdlp still forces node runtime", "--js-runtimes" in src)

# 5. extension-agnostic detection
play_dir = yt.DOWNLOAD_DIR  # module-global "downloads" (relative to CWD)
os.makedirs(play_dir, exist_ok=True)
probe = os.path.join(play_dir, "TESTVID999.webm")
with open(probe, "wb") as f:
    f.write(b"1234567890")
found = yt._find_downloaded_file("TESTVID999", "audio")
check("extension-agnostic finder finds .webm", found == probe)
try: os.remove(probe)
except OSError: pass

# 6. playback path stays local-file-only (no get_stream_url handed to client.play)
play_src = open(os.path.join(PYLIB, "plugins", "play.py")).read()
calls_src = open(os.path.join(PYLIB, "core", "calls.py")).read()
check("play.py no get_stream_url() assignment on playback", "file_path = stream_url" not in play_src and "get_stream_url(" not in play_src)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
