# GGF standalone app build and handoff guide

Read this first when starting or updating a GGF app in this workspace.
Existing architecture reference: COMFY-CORE-APP-STANDARD.md.
Current examples: bfs-swap/FLoyd-Headliner/Floyd-Headliner,
ltx25/LTX25-Core-Studio, ggf-video-likeness/GGF-Video-Likeness.
Bernini/GGF-Bernini is the new video-editing example.

## Product and UI

Name the app for the user's outcome. GGF is the product family; underlying
models are a smaller Powered by footer, not the main title. Preserve the
navy/gold design already used by Headliner and Spokesman. Copy their actual
CSS and controls, not a newly invented visual system.

- Background #07101f; cards #111c2f; inputs #091425; text #e8eef9.
- Gold primary buttons #f5b942 with dark #091425 text. Secondary #192d47.
- Dropdown options must have explicit readable background AND foreground.
- Set the Gradio theme's light AND dark label/background/text variables to the
  same approved palette, so light-theme clients cannot create white labels
  with light text. Test upload labels as well as dropdowns and ordinary fields.
- Gradio 6 scopes media-query selectors under .contain, so ancestor selectors
  for .main or .gradio-container will not match there. Use top-level fluid
  clamp() padding for outer wrappers and breakpoint rules for inner controls.
- Segoe UI / Inter / Arial, readable 16px mobile inputs. Small mobile logo;
  compact header, wrapping links, fluid controls, no horizontal overflow.
- Primary tab: inputs, short instructions, prompt, necessary size/time controls,
  Turbo above full-size Generate, Stop, status, tall output with fullscreen.
- Settings: model status, advanced knobs, updates, and phone/network access.
- Reuse GetGoingFast.pro and youtube.com/@TheAIHobbyGuy links and brain logo.
- Keep controls purpose-built. Avoid redundant outputs and approval gates.
- Detect portrait/landscape using displayed rotation-aware dimensions.
- Defaults can be short/fast, but do not impose arbitrary total-duration caps.

## Runtime

Import selected upstream model loaders, conditioning, sampler, and VAE code
inside an APP-OWNED Python worker. Bundle only required inference modules
under vendor/comfy_core. Do not require, find, start, or call a ComfyUI server.
Do not ship ComfyUI browser frontend or custom-node manager. Keep upstream
licenses, pinned source commits, and notices. This approach does not remove
upstream licensing obligations or model-specific licenses.

Each app owns its environment/configuration/model paths. Never patch another
app's environment. For local development, models and environments may live on
E: with junctions inside the D: app; CUSTOMER DEFAULTS must be app-relative.
Reuse existing model files only after validating filenames, sizes and hashes.

One GPU worker at a time per app, including local and public views. JSON-line
protocol carries progress/results; diagnostics go to job-specific logs.
Release worker process/VRAM after each job unless measured caching is justified.
Stop must terminate only the app-owned worker and its venv child tree.
Do not kill unrelated services. Check for a running job before restart.

Use no_grad for core sampling unless its exact code permits inference_mode:
inference tensors can fail when Comfy adjusts version counters.
Match the real workflow scheduler, guidance, step split, conditioning and
LoRA strengths. Treat acceleration wheels as optional until they import and
complete a REAL generation with the exact pinned Torch/CUDA environment.
Never claim speed or successful inference solely from imports or UI startup.

## Phone, persistence, progress

Local loopback UI always stays login-free. A separate remote Gradio UI uses
the same backend lock and optional login. Blank password explicitly disables
remote authentication. Settings apply on restart. Bind with port fallback;
give different apps different preferred local/remote ranges.

Browser-owned random workspace token is persisted in localStorage; restore
with ONE load handler. Do not combine a callable gr.State initializer with
restoration: competing load handlers overwrote saved state in Headliner.
Persist uploads outside Gradio's disposable cache plus controls/results in
jobs/workspaces. New public URLs are separate browser origins: old localStorage
does not transfer, though files remain on disk.

Start generation by clearing only the displayed old result. Keep saved files.
Persistent activity banner shows elapsed time, model stage/sampling step,
completion/error/interruption. Disable generation buttons while owned job runs.
Use unique timestamp+random filenames for downloads, preserving paths through
worker result JSON, workspace, and Gradio output. Avoid result.mp4 for exports.
Normalize saved dropdown values during migration. UI component ID changes
require a freshly loaded page after restart to prevent stale request inputs.
Handle interrupted multipart uploads with a clear retry error; never generate
from incomplete input. Gradio mobile/native fullscreen needs browser testing.

## Installers, updates, packages

Single CMD installer beside the app: ./INSTALL.bat and ./GGF-App/app.py.
No PowerShell installation logic. The installer creates a private venv,
installs CUDA Torch separately from ordinary requirements, downloads pinned
models with resume, verifies size/hash, and preserves partial downloads.
RUN.bat launches from its own directory; type assets/about.nfo if it exists.
UPDATE.bat delegates update logic to Python so existing BATs need fewer changes.

Use the original Headliner method: push individual source files to Codeberg
(primary) and GitHub. Download the hosts' automatically generated repository
archives, preferably pinned to the revision returned by the branch API.
Never put a manually maintained source ZIP in a repository or make updates
depend on rebuilding one. Customers do not need Git for app updates.
Check repository revisions so a source commit is detectable without a version
bump. Validate paths and required app files; stage before copying and back up
existing source. Preserve models, jobs, environments and private configuration.
Customer installer ZIPs are separate distribution packages. Drive may hold a
backup, but must not become a manually rebuilt prerequisite for code updates.
Publish both source repositories and verify their revisions and archive content.

Build installer ZIP from an explicit allowlist; preserve the prior ZIP first.
Scan archive entries to prove private-file exclusion. Keep production filename
stable. Record exact folder, commands, versions, checks, current link, unresolved
issues, source commits, release destinations and file IDs in the app handoff.

Never delete a file or folder without explicit user permission. A cleanup
request applies to identified disposable targets, not arbitrary apps/models.
This document is workspace guidance, not a memory database update.
