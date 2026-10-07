# GGF Bernini handoff — October 6, 2026

## Update-system correction — October 7, 2026

The app now publishes individual source files at Codeberg Cognibuild/GGF-Bernini
and GitHub gjnave/GGF-Bernini. update_app.py downloads the automatically generated
repository archive for the current commit. Settings includes Update and restart.
No manually maintained source ZIP or release manifest is required. The old
archive-only/development-mirrors notes below describe the initial build and are
superseded by this correction. Public packages exclude models, environment,
private settings, generated media, and source-control metadata.

## Exact locations

- App: D:/apps2review/Bernini/GGF-Bernini
- Installer/RUN/UPDATE and ZIPs: D:/apps2review/Bernini
- Local development environment: E:/GGF-Runtimes/Bernini, junction at app/.venv
- Local verified models: E:/GGF-Models/Bernini, junction at app/models
- Customer paths default to app-relative .venv and models, not developer paths.
- Root reusable guide: D:/apps2review/GGF-APP-BUILD-GUIDE.md.
- Provided source cloned for research at ../research-source, never needed to run.

## What is built

GGF navy/gold Gradio interface, mobile fluid padding and readable labels/options,
video + optional reference + optional edit prompt, rotation-aware source shape,
start/duration, full-size and half-size Turbo above Generate, Ctrl+Enter Turbo,
six-step HIGH/LOW sampling, LightX2V speed adapter, progress/stage/elapsed banner,
Stop that terminates only the owned worker, unique video download filenames,
tall output/fullscreen, original-audio muxing, durable browser workspaces,
Settings for advanced controls, model checks, network access and update check.

No ComfyUI server/application/frontend is required. The worker imports pinned
core modules and BerniniConditioning directly. Wan core already has native
context_latents support. No KJNodes/VHS installation is needed: app media helpers
replace those workflow conveniences. Bernini model source changed upstream:
the current source bundle uses Comfy-Org/Bernini-R HIGH/LOW FP8, not old Kijai
Bernini filenames. Pinned metadata/hashes are in model_manifest.json.

## Verified environment and inference

Python 3.11.15, Torch 2.10.0+cu130, torchvision 0.25.0, torchaudio 2.10.0,
Gradio 6.29.0, comfy-kitchen 0.2.35, comfy-aimdo 0.5.5, RTX 4090 24 GB.
All five model sizes/SHA256 values verified. pip check passed.
Native Torch SDPA attention is the validated route; no acceleration wheel
combination has been added to this new environment.

- 1 second, 128×128, 24 frames, six steps, reference 256: 36.55 seconds;
  peak allocated VRAM 14.81 GiB; MP4 decoded successfully.
- Default Turbo 3 seconds, 256×256, 72 frames, six steps, reference 640:
  49.06 seconds; peak allocated VRAM 15.73 GiB; MP4 decoded successfully.
- Input sample is square, 768×768, 25 fps, 5.16 seconds, no audio. Thus these
  timing tests do not constitute real-audio preservation verification.
- Output inspection confirmed the source blonde subject/clothing changed to
  the reference's red-haired subject/denim look while retaining the scene.
  This is a generative edit, not exact pixel preservation or face tracking.
- Three CPU tests cover legacy-shape migration/workspace restoration,
  progress callback disconnect handling, and Turbo request/display clearing.
- Browser Settings tab and all model checks rendered; labels explicitly
  use light text against dark panels. Mobile viewport 390×844 checked.

Important correction: Wan VAE decode returns B,T,H,W,C in this pinned core.
worker removes the single batch dimension before passing T,H,W,C to MP4 encoder.
Do not regress to slicing the outer batch as if it were the frame axis.

## Runtime, limitations, release

Preferred local port 7864, remote port 8864; occupied ports are retried.
The local UI is always login-free. Development remote mode is a temporary
public link with blank password; customers default to local-only because
private network_settings.json is excluded from packages.
Use the actual startup log for the current public URL; it changes on restart.

App-owned worker ends after each generation, releasing VRAM. Both model stages
are sequential. Video is currently encoded/decoded as a whole clip in RAM.
Long durations have no arbitrary hard cap but can exceed memory. Defaults are
three seconds; reduce size/duration on OOM. Do not call low-VRAM GPUs validated.
Full-size 480p generation has not been separately benchmarked in this build.

The source updater supports verified ZIP staging, source backups, safe paths,
and preservation of models/jobs/config/environment. release_sources.json is
intentionally empty until this NEW APP is published to its own approved mirrors.
Do not point it at Headliner or overwrite bernini-comfy-standalone's old ComfyUI
installer repository. A remote update is not operational until mirrors are
configured, uploaded and read back. Local source archive updates work now:
UPDATE.bat "path/to/GGF-Bernini-source.zip" (app closed).

Build ZIPs with .venv/Scripts/python.exe ../package_release.py. Source excludes
private paths and BATs; installer ZIP adds only INSTALL/RUN/UPDATE at its root.
Existing archives are backed up before rebuild. Recheck manifests after edits.
No GitHub/Codeberg/Drive publication of Bernini was performed in this build.
