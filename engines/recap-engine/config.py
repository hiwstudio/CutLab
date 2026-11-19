"""Central configuration for the Recap Engine (separate, isolated system)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Project .env first, then the machine-wide ~/.env (API keys only). Neither
    # overrides an already-set variable, so precedence is:
    # real environment > project .env > global ~/.env.
    load_dotenv(Path(__file__).parent / ".env")
    load_dotenv(Path.home() / ".env")
except Exception:
    pass

# --- Paths ---
ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"

# --- Transcription (local faster-whisper) ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "auto")

# --- Downloads (reused from clip engine) ---
DL_MAX_RES = int(os.getenv("DL_MAX_RES", "1080"))
YT_BROWSER = os.getenv("YT_BROWSER", "")

# --- Story brain (LLM) ---
# backend: "openrouter" = automatic API, "manual" = file hand-off (run prompts
# through Claude Code / Claude, drop the answer back for the engine to resume).
LLM_BACKEND = os.getenv("LLM_BACKEND", "manual")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4.5")
# Map-reduce outline: ~chars of timestamped transcript per chunk (a film won't
# fit one context window). ~8000 chars ≈ 2k tokens, with a small overlap so a
# beat spanning a chunk boundary isn't lost.
OUTLINE_CHUNK_CHARS = int(os.getenv("OUTLINE_CHUNK_CHARS", "8000"))
OUTLINE_CHUNK_OVERLAP = int(os.getenv("OUTLINE_CHUNK_OVERLAP", "400"))

# --- Recap shape ---
# Standard window for LONG sources (>= 60 min), which recap automatically to this
# range. Short sources don't use this window - run.py prompts for a length and
# that choice defines its own acceptance band (see run._resolve_length).
RECAP_MIN_MINUTES = int(os.getenv("RECAP_MIN_MINUTES", "12"))
RECAP_MAX_MINUTES = int(os.getenv("RECAP_MAX_MINUTES", "22"))
# Length policy (owner's decision): ACCEPT the natural TTS duration. After TTS we
# measure the real narration length and simply keep it - the recap is however
# many minutes it naturally comes in at. We do NOT rewrite/expand/compress beats
# to force a target, because padding or trimming the narration to hit a number
# compromises the writing; the natural length is cleaner.
# Set RECONCILE_LENGTH_REWRITE=1 to re-enable the old rewrite-to-window loop.
RECONCILE_LENGTH_REWRITE = os.getenv("RECONCILE_LENGTH_REWRITE", "0") == "1"
# Max rewrite passes IF RECONCILE_LENGTH_REWRITE is on (legacy behavior).
RECONCILE_MAX_PASSES = int(os.getenv("RECONCILE_MAX_PASSES", "3"))

# Outline granularity: how many story beats to aim for per MINUTE of finished
# recap. This is the pacing dial that actually matters. Each beat is one stretch
# of narration over one matched piece of footage, so beats-per-minute IS how
# often the picture gets re-pointed at what is being said.
# Measured 2026-09-03: the 31-beat / 16.4-min recap spent ~31s per beat, which is
# why 35% of its shots held past 8 seconds and the picture drifted from the
# words. 3.5 beats/min puts a beat at ~17s - denser coverage, each beat still
# tied to its own moment. This is the RIGHT way to get a faster cut: more,
# smaller beats - NOT widening each beat's footage pool, which is what made the
# rejected v2 wander (see the POST-MORTEM in CLAUDE.md).
OUTLINE_BEATS_PER_MINUTE = float(os.getenv("OUTLINE_BEATS_PER_MINUTE", "3.5"))

# --- Scene detection ---
SCENE_THRESHOLD = float(os.getenv("SCENE_THRESHOLD", "0.30"))  # ffmpeg scene score 0-1
SCENE_MIN_LEN = float(os.getenv("SCENE_MIN_LEN", "1.5"))       # merge shots shorter than this (s)
# The scene score is a CONTRAST difference, so one fixed threshold is really a
# fixed assumption about how bright a film is - and a dark film breaks it. On
# The Invisible Man (2020) the 0.30 default found 2 cuts in a ten-minute opening
# of ~30 shots, leaving 57 of 124 minutes inside 18 giant "scenes"; several
# recap beats then collapsed onto the same block and would have shown the same
# footage repeatedly. So detection measures how much of the runtime is still
# stuck in cut-free blocks longer than SCENE_BLIND_CAP_SECONDS, and if more than
# SCENE_BLIND_MAX_SHARE of the film is, it retries at a lower threshold.
SCENE_BLIND_CAP_SECONDS = float(os.getenv("SCENE_BLIND_CAP_SECONDS", "60"))
SCENE_BLIND_MAX_SHARE = float(os.getenv("SCENE_BLIND_MAX_SHARE", "0.15"))
SCENE_THRESHOLD_STEP = float(os.getenv("SCENE_THRESHOLD_STEP", "0.5"))
SCENE_THRESHOLD_RETRIES = int(os.getenv("SCENE_THRESHOLD_RETRIES", "3"))

# Seconds of the SOURCE to treat as off-limits for recap footage. Feature files
# open with distributor and production idents - The Invisible Man runs Universal
# then Blumhouse for 33 seconds - and a beat anchored at t=0 will happily match
# them, so the recap opens on somebody else's logo. Set this to where the film
# actually starts. 0 = use everything.
SOURCE_SKIP_SECONDS = float(os.getenv("SOURCE_SKIP_SECONDS", "0"))

# --- Footage understanding (scene cards + vision) ---
# All local + free via onnxruntime (no torch). CLIP gives a joint image<->text
# space so narration can be matched to the most visually-relevant scene, even
# when the scene has little or no dialogue. A small text model handles
# dialogue<->narration similarity for talky scenes.
EMBED_TEXT_MODEL = os.getenv("EMBED_TEXT_MODEL", "BAAI/bge-small-en-v1.5")
CLIP_VISION_MODEL = os.getenv("CLIP_VISION_MODEL", "Qdrant/clip-ViT-B-32-vision")
CLIP_TEXT_MODEL = os.getenv("CLIP_TEXT_MODEL", "Qdrant/clip-ViT-B-32-text")
# Keep the downloaded ONNX models with the project (persists across TEMP cleanup,
# fits the isolated-system rule). ~730MB one-time download.
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", str(ROOT / "models"))
KEYFRAME_WIDTH = int(os.getenv("KEYFRAME_WIDTH", "384"))   # downscale keyframes for CLIP
DIALOGUE_MIN_WORDS = int(os.getenv("DIALOGUE_MIN_WORDS", "4"))  # below = "visual" scene

# --- Beat -> scene matching ---
# Each candidate scene is scored by: how close it is in time to where the beat
# happens (strong prior), how well its keyframe matches the narration (CLIP),
# and how well its dialogue matches the narration (text). Tunable weights.
MATCH_W_TIME = float(os.getenv("MATCH_W_TIME", "0.5"))
MATCH_W_VISUAL = float(os.getenv("MATCH_W_VISUAL", "0.35"))
MATCH_W_DIALOGUE = float(os.getenv("MATCH_W_DIALOGUE", "0.15"))
MATCH_TIME_WINDOW = float(os.getenv("MATCH_TIME_WINDOW", "180"))  # coarse +/- window (s)
# Scenes a beat may draw on. Since the assembler takes only a SHORT piece of each
# scene (SHOT_MAX_SECONDS), a 40-second beat legitimately needs ~10-14 scenes to
# be cut properly - the old cap of 6 forced long unbroken holds.
MATCH_MAX_SCENES_PER_BEAT = int(os.getenv("MATCH_MAX_SCENES_PER_BEAT", "6"))
# After the real narration length is known, every beat's footage must fully cover
# its voiceover (plus this safety margin) or the picture would run out before the
# narration does. The coverage stage extends a beat across more consecutive scenes
# until it clears this; it is NOT capped by MATCH_MAX_SCENES_PER_BEAT.
COVERAGE_MARGIN_SECONDS = float(os.getenv("COVERAGE_MARGIN_SECONDS", "0.5"))

# --- Voiceover (TTS) ---
# piper = local/free/offline; fish = Fish Audio HTTP API (better narration voice,
# needs FISH_API_KEY - read from ~/.env by default).
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper")     # piper | fish | none
PIPER_VOICE = os.getenv("PIPER_VOICE", "")        # path to a Piper .onnx voice model

# Fish Audio (https://api.fish.audio). NOTE: on the free model (s2.1-pro-free) a
# reference_id is rejected with 400 "Reference not found" - custom/public voices
# are a paid-tier feature, so leave FISH_VOICE_ID empty on free and you get the
# default voice. Paid models (s1, s1-mini, speech-1.6, s2.1-pro) need credit.
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_MODEL = os.getenv("FISH_MODEL", "s2.1-pro-free")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "")    # reference_id; paid tier only
FISH_FORMAT = os.getenv("FISH_FORMAT", "wav")     # wav keeps the master lossless
# Delivery speed (Fish prosody.speed; 1.0 = the voice's own pace).
# Measured 2026-09-04: at 1.0 this voice reads recap prose at ~225-247 wpm.
# The five reference channels narrate at 151-205 wpm, and the two biggest
# sit at the SLOW end (167, 151). 0.85 puts us at ~209 - unrushed, and
# still the fastest end of professional. Affects pace, not length policy.
FISH_SPEED = float(os.getenv("FISH_SPEED", "0.85"))
FISH_RETRIES = int(os.getenv("FISH_RETRIES", "4"))  # SSL EOFs are common mid-batch
# Words-per-minute used to budget the script's length. Set to the TTS engine's
# MEASURED reading rate (both read faster than a human ~165 wpm), so the initial
# script is budgeted realistically and the natural TTS duration lands near the
# requested minutes on its own - no rewrite pass needed. Measured ~200-205 wpm on
# the Piper lessac voice and ~199 wpm on Fish s2.1-pro-free, so one default fits
# both. Every TTS run logs the measured rate; if it drifts, override here.
NARRATION_WPM = int(os.getenv("NARRATION_WPM", "200"))

# --- Publishing assets (captions + thumbnails) ---
# After the recap is assembled, the engine also produces publish-ready assets so
# every finished project can be uploaded immediately. Both stages cache to the
# workdir and resume like every other stage.
CAPTION_PLATFORMS = ["youtube", "tiktok", "facebook", "x"]
# How many distinct thumbnail concepts to propose (each picks a real frame).
THUMBNAIL_COUNT = int(os.getenv("THUMBNAIL_COUNT", "5"))
# Art style that thumbnail ENHANCEMENT prompts must stay consistent with. After
# the concepts are chosen, the engine writes an image-generation prompt per
# concept to elevate each frame into a polished YouTube thumbnail WITHOUT
# changing its idea/composition. Override to match your channel's look.
THUMBNAIL_ART_STYLE = os.getenv(
    "THUMBNAIL_ART_STYLE",
    "cinematic, photorealistic, high-detail, natural filmic color grade",
)
# The channel's thumbnail TEXT style, baked into enhancement prompts.
# DEFAULT IS EMPTY - no text at all - on measured evidence, not taste.
# 2026-09-03: inspected the top-4 thumbnails of all five reference channels
# (11 distinct images, 17k-6.1M views). NOT ONE carried any text. Every one is a
# single extreme, legible image that poses a question - a man on a mountain of
# cash, a couple asleep under banknotes, a lone robber walking out through a SWAT
# cordon. The title carries the words; the thumbnail carries the image.
# Set THUMBNAIL_TEXT_STYLE to a style string to turn overlays back on.
THUMBNAIL_TEXT_STYLE = os.getenv("THUMBNAIL_TEXT_STYLE", "")

# --- Output video ---
OUT_WIDTH = int(os.getenv("OUT_WIDTH", "1920"))   # 16:9 classic recap by default
OUT_HEIGHT = int(os.getenv("OUT_HEIGHT", "1080"))
OUT_FPS = int(os.getenv("OUT_FPS", "24"))         # normalize all beats to this fps

# Final-output H.264 encode (the size-determining pass = per-beat voiced segments,
# which the concat then STREAM-COPIES, so these settings decide the recap's size).
#
# QUALITY IS LOCKED to the original CRF 21 with NO bitrate cap - visually the same
# perfect output as before. The ONLY size lever we use is the encoder PRESET, which
# is LOSSLESS: at a fixed CRF the preset changes how hard the encoder works to hit
# that exact quality, not the quality itself. A slower preset => smaller file at
# identical quality (costs encode time only). "slow" trims ~15% off "fast" with no
# perceptual change (verified by SSIM). Do NOT raise CRF or add a maxrate cap here
# unless the owner explicitly asks - that would trade away quality.
VIDEO_CRF = int(os.getenv("VIDEO_CRF", "21"))
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "slow")    # LOSSLESS size lever (time only)
VIDEO_MAXRATE = os.getenv("VIDEO_MAXRATE", "")      # no cap by default (quality-safe)
VIDEO_BUFSIZE = os.getenv("VIDEO_BUFSIZE", "")
# Throwaway footage intermediate (re-encoded by the segment pass). Kept visually
# lossless (CRF 18) so it never adds any generational loss to the final, and fast
# since it is temporary and deleted-able.
VIDEO_INTERMEDIATE_CRF = int(os.getenv("VIDEO_INTERMEDIATE_CRF", "18"))
VIDEO_INTERMEDIATE_PRESET = os.getenv("VIDEO_INTERMEDIATE_PRESET", "veryfast")

# How far the film's own audio is ducked under the narration.
# MEASURED 2026-09-03 (scientist/projects/movie-recap-craft-2026): professional
# recaps run a loudness RANGE of 2.9-3.2 LU; ours was 1.3 LU at the same
# integrated level, i.e. a mix where nothing ever moves. Cause: -25 dB puts the
# film's score and ambience below audibility, so a long shot is carried by
# literally nothing. Every channel measured either keeps the film audio live
# under the voice (MrRecap, Pavel) or replaces it with a continuous music bed
# (Mavrix). -14 dB keeps the film present without fighting the narrator.
DUCK_ORIGINAL_DB = int(os.getenv("DUCK_ORIGINAL_DB", "-25"))

# --- Copyright-safety transform (from the "movie recap method" video, 2026-09-09)
# His CapCut rules, now automated. Public datapoint: the SAME edit survived
# Content ID at ~37s and was struck at ~1:23. That is a fingerprint dodge, not
# legal advice, and a 12-22 min recap is outside what he measured. We still
# apply the transform to every movie-recap beat because it is the only method
# we have that he showed working at all.
#
# 1. MUTE_FILM_AUDIO - always mute the film. ffmpeg `volume=0` is LINEAR mute
#    (samples become silence, stream kept so concat params stay uniform).
#    `volume=0dB` is a no-op — that bug shipped on 2026-09-09 and is the
#    opposite of mute. Do not put a `dB` suffix on the mute path.
# 2. DROP_ALTERNATE_SHOTS + SHOT_SPLIT_SECONDS - the 3-second rule THEN delete
#    every second clip (keep 0-3, drop 3-6, keep 6-9, ...). This is NOT the
#    pacing stride in `_shot_list`. Coverage must gather ~2x narration so the
#    kept half still covers the voice.
# 3. FLIP_ALTERNATE_SHOTS - one hflip orientation PER SOURCE SCENE (his rule
#    #4, adapted). Flipping every 3s keep inside a locked shot makes a person
#    on the left jump to the right every clip. Consecutive scenes still
#    alternate so ~half the picture is mirrored; returning to a scene later
#    keeps the same orientation.
# 4. FIT_BY_SPEED - retime to the narration; never freeze or loop when the
#    drop-alternate transform is on (a loop repeats the fingerprint).
# Extra suite on top of his rules (movierecap profile): a small zoom and a
# mild grade so even the un-flipped 3s keeps are not pixel-identical to the
# reference. Not a substitute for mute + drop + flip.
MUTE_FILM_AUDIO = os.getenv("MUTE_FILM_AUDIO", "1") == "1"
DROP_ALTERNATE_SHOTS = os.getenv("DROP_ALTERNATE_SHOTS", "0") == "1"
SHOT_SPLIT_SECONDS = float(os.getenv("SHOT_SPLIT_SECONDS", "3"))
FLIP_ALTERNATE_SHOTS = os.getenv("FLIP_ALTERNATE_SHOTS", "0") == "1"
FIT_BY_SPEED = os.getenv("FIT_BY_SPEED", "1") == "1"
FIT_BY_SPEED_MAX_SLOW = float(os.getenv("FIT_BY_SPEED_MAX_SLOW", "1.25"))
# Extra fingerprint layers. 1.0 / off = no change (non-movie recaps).
COPYRIGHT_ZOOM = float(os.getenv("COPYRIGHT_ZOOM", "1.0"))
COPYRIGHT_GRADE = os.getenv("COPYRIGHT_GRADE", "0") == "1"
# Informational cap for any Shorts cut of a recap. The main recap length stays
# owner-locked (natural TTS). His strike window was ~1:23; stay under ~40s.
SHORTS_MAX_SECONDS = float(os.getenv("SHORTS_MAX_SECONDS", "40"))

# Film audio level during a DIALOGUE BEAT - a beat with no narration where the
# film is allowed to play its own line (see story.write_recap_script). 0 = full.
# MUTE_FILM_AUDIO wins: a dialogue beat with mute on is silent picture.
DIALOGUE_BEAT_DB = int(os.getenv("DIALOGUE_BEAT_DB", "0"))


def usable_footage_seconds(duration: float) -> float:
    """Seconds the assembler will actually KEEP from a scene of this length.

    DROP_ALTERNATE_SHOTS keeps every other 3s clip (~half). Otherwise a
    SHOT_MAX_SECONDS cap (pacing sub-cut) applies. Coverage and gather MUST
    use this, or they will declare a beat covered while the assembler throws
    half the picture away and the voice outruns the film.
    """
    d = max(0.0, float(duration))
    if DROP_ALTERNATE_SHOTS:
        return d * 0.5
    if SHOT_MAX_SECONDS > 0:
        return min(d, SHOT_MAX_SECONDS)
    return d

# Fill the 16:9 frame by cropping, instead of letterboxing a wider source.
# DEFAULT OFF. The reference channels do fill the frame, but cropping a 2.39:1
# scope film to 16:9 throws away 26% of the WIDTH and wrecks the framing - on
# Disclosure Day it cut figures in half at both edges and shoved the subject off
# centre. Letterboxing preserves the director's composition, which matters more.
FILL_FRAME = os.getenv("FILL_FRAME", "0") == "1"

# Direct the edit BEFORE writing narration (story.plan_shots), then write the
# script to those shots. DEFAULT OFF: on its first real outing this produced a
# measurably tighter cut and noticeably WORSE narration - flat, list-like prose
# that read as stage directions, and beats whose footage roamed twice as far from
# what the words described. Kept for experiments; see CLAUDE.md.
DIRECT_SHOTS = os.getenv("DIRECT_SHOTS", "0") == "1"

# --- Shot pacing (measured 2026-09-03) ---
# Professional recaps cut every 1.5-2.4s and hold under 2% of shots past 8s.
# Our old one-continuous-span-per-beat build measured 5.3s median with 35% of
# shots past 8s - the "picture stalls while the voice keeps going" defect. The
# assembler now sub-cuts each beat's scene run into shots of at most
# SHOT_MAX_SECONDS, skipping SHOT_LEAD_SECONDS of each scene's head (cut points
# are usually the least interesting frames of a shot).
# CORRECTED 2026-09-06: the first version of _shot_list cut correct-length
# pieces that were ADJACENT in the source, and `select` can only keep frames in
# time order - so they played back as one continuous shot and the cut never
# appeared. 10 pieces of <=2.4s became 3 visible runs of 8.7s, 2.4s and 12.0s.
# Pieces are now SPREAD with a stride so every boundary is a real cut; a beat
# without ~1.1x its narration in footage falls back to a continuous span rather
# than looping. Measured after the fix on The Invisible Man: median visible shot
# 2.40s, 2.5% over 8s (was 35%).
# Set SHOT_MAX_SECONDS=0 to restore the old single-span behaviour.
SHOT_MAX_SECONDS = float(os.getenv("SHOT_MAX_SECONDS", "0"))
SHOT_MIN_SECONDS = float(os.getenv("SHOT_MIN_SECONDS", "1.2"))
SHOT_LEAD_SECONDS = float(os.getenv("SHOT_LEAD_SECONDS", "0.3"))

# Shortest a planned beat may be. Each beat's share of the runtime is
# proportional to the source time it covers, so a glancing moment can otherwise
# be allotted three seconds of narration.
PLAN_MIN_BEAT_SECONDS = float(os.getenv("PLAN_MIN_BEAT_SECONDS", "12"))

# How many DIALOGUE BEATS to aim for - moments where the narrator stops and the
# film plays its own line. The largest channel measured uses them continuously;
# two of five use none at all, so this is a dial, not a law. 0 disables them.
DIALOGUE_BEATS = int(os.getenv("DIALOGUE_BEATS", "0"))

# --- Movie-recap profile (RECAP_PROFILE=movierecap) -------------------------
# An opt-in editing profile for MOVIE recaps. Other channels and formats keep
# the engine's defaults untouched: nothing below applies unless the profile is
# named. See docs/profiles/movierecap.md for the full brief.
#
# Two things it changes:
#   1. Pacing. Turns on the shot sub-cutting the engine already measured as
#      correct (see "Shot pacing" above) and raises the per-beat scene pool that
#      sub-cutting needs, because the cap of 6 forces long unbroken holds.
#   2. Treatments. A post-assembly pass (engine/treatments.py) that breaks up
#      the picture: same-scene silent inserts, stills, punch-in crops, motion
#      and typography - audio never touched.
RECAP_PROFILE = os.getenv("RECAP_PROFILE", "")

# Cadence: one treatment per this many seconds of finished recap.
TREAT_EVERY_SECONDS = float(os.getenv("TREAT_EVERY_SECONDS", "30"))
TREAT_MIN_SECONDS = float(os.getenv("TREAT_MIN_SECONDS", "2"))
TREAT_MAX_SECONDS = float(os.getenv("TREAT_MAX_SECONDS", "5"))
# How far from the beat's own footage an insert may be drawn. The insert must
# read as the SAME scene, so this is deliberately tight: a cutaway from another
# location is a continuity error, not a treatment.
TREAT_SCENE_WINDOW = float(os.getenv("TREAT_SCENE_WINDOW", "75"))
# Hard ceiling on how far a chosen insert may sit from the beat's own footage.
# The window above is the search area; this is the accept/reject line. Measured
# on The Invisible Man: with no ceiling, a beat at 96-149s was answered with a
# shot from 35s - a different scene of the film. A slot with nothing closer than
# this is SKIPPED. Fewer treatments beats a continuity error.
TREAT_MAX_GAP = float(os.getenv("TREAT_MAX_GAP", "20"))
# Punch-in crop factor for the `crop` treatment. 1.0 = no crop.
TREAT_CROP_ZOOM = float(os.getenv("TREAT_CROP_ZOOM", "1.4"))
# Ken Burns push applied to `still` treatments, as a fraction of frame over the
# life of the still. 0 = a hard freeze with no movement.
TREAT_STILL_PUSH = float(os.getenv("TREAT_STILL_PUSH", "0.08"))
# Rotation of treatment kinds. Repetition is the failure mode the owner called
# out, so the planner walks this cycle instead of picking one kind.
TREAT_CYCLE = os.getenv("TREAT_CYCLE", "insert,crop,still,insert,motion,typography")
TREAT_FONT = os.getenv("TREAT_FONT", "")          # .ttf for typography; blank = engine default
TREAT_FONT_SIZE = int(os.getenv("TREAT_FONT_SIZE", "64"))


def apply_profile() -> None:
    """Fold the named profile's overrides into this module.

    Called once at startup. An env var the user set explicitly always wins, so a
    profile is a set of DEFAULTS, not a straitjacket - `SHOT_MAX_SECONDS=3.5
    RECAP_PROFILE=movierecap` gives you 3.5.
    """
    global SHOT_MAX_SECONDS, MATCH_MAX_SCENES_PER_BEAT, OUTLINE_BEATS_PER_MINUTE
    global FLIP_ALTERNATE_SHOTS, DROP_ALTERNATE_SHOTS
    global COPYRIGHT_ZOOM, COPYRIGHT_GRADE
    if RECAP_PROFILE != "movierecap":
        return
    if "SHOT_MAX_SECONDS" not in os.environ:
        SHOT_MAX_SECONDS = 2.4      # measured pro range is 1.5-2.4s
    if "MATCH_MAX_SCENES_PER_BEAT" not in os.environ:
        MATCH_MAX_SCENES_PER_BEAT = 14   # sub-cutting needs a deeper pool than 6
    if "OUTLINE_BEATS_PER_MINUTE" not in os.environ:
        OUTLINE_BEATS_PER_MINUTE = 3.5
    # His copyright rules (3s keep/drop + flip remaining). Mute is already
    # default-on for every recap; these two only belong on movie recaps.
    if "DROP_ALTERNATE_SHOTS" not in os.environ:
        DROP_ALTERNATE_SHOTS = True
    if "FLIP_ALTERNATE_SHOTS" not in os.environ:
        FLIP_ALTERNATE_SHOTS = True
    if "COPYRIGHT_ZOOM" not in os.environ:
        COPYRIGHT_ZOOM = 1.08
    if "COPYRIGHT_GRADE" not in os.environ:
        COPYRIGHT_GRADE = True
