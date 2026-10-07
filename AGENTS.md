# GGF Bernini

Publish individual files to Codeberg Cognibuild/GGF-Bernini and GitHub gjnave/GGF-Bernini.
Updates use host-generated repository archives like original Headliner; never
require a manually rebuilt source ZIP or manifest. Check repository revisions.
Customer installer ZIPs belong in the member download folder, not the repositories.

Read D:/apps2review/GGF-APP-BUILD-GUIDE.md before app work.
Only modify this app and its parent installer/package scripts.
Never delete files or folders without explicit permission.
Preserve GGF navy/gold UI, compact mobile view, phone settings, optional password,
login-free local UI, browser workspaces, generation banner, Stop, and unique exports.
Bernini is video editing using source video + optional reference + text.
Do not use a ComfyUI server. Worker imports vendor/comfy_core and vendor/bernini.
HIGH and LOW FP8 models run in sequence, with six steps split 3+3 and
LightX2V strengths 3 / 1.5 from the supplied workflow. No other LoRAs by default.
Default full short edge 480, Turbo half dimensions, 3 seconds; no duration cap.
Upstream GPL licenses and model notices must remain.
Source excludes environments, models, jobs, logs, local/network configs,
installer BATs, and installer ZIPs. See HANDOFF.md for exact verified state.
