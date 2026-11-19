# MixFix in CutLab

CutLab includes the MixFix source and the MIX/FIX project adapter. Start a
MixFix run with `scripts\engine.ps1 mixfix run ...`, approve it in its review
board, then import it from CutLab's home screen. An imported project remains
editable as an EDL with separate footage, narration, and caption tracks.

The adapter uses `engines/mixfix` by default. Set `CUTLAB_MIXFIX_ROOT` if you
choose to keep a separate MixFix checkout. Source projects stay in MixFix;
CutLab copies the required media into its own project storage and records the
source link and provenance.

The current direct adapter supports MIX and FIX. The standalone Split engine is
included and can be used with the same launcher. MixFix crossfades, SPLIT
project import, automatic regeneration dispatch, and live two-way project sync
are not translated into CutLab edits yet.
