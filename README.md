# GGF Bernini

Settings includes **Release models / free GPU memory** and **Stop server**.
Release keeps the app and phone connection open; Bernini already unloads its
worker after each finished job. Stop server asks for confirmation and requires
restarting RUN.bat on the local PC. Finish or cancel active generation first.

**Reshape your video. Keep the performance.**

Get going fast with [GGF tools and setup helpers](https://getgoingfast.pro)
and [The AI Hobby Guy on YouTube](https://youtube.com/@TheAIHobbyGuy).

Upload a video, optionally add a reference photo, and describe what should
change. Generate a Turbo preview or a full-size edit. The app retains source
audio and saves each result with a unique download filename.

The main page is kept simple. Settings contains model checks, sampling controls,
updates, and phone access. Choose Temporary public link, optionally set a
username/password, save, and restart. Local access always remains login-free.
Blank remote password disables login. Public links are temporary.

Displayed input orientation is automatically respected. Defaults: 3 seconds,
480 short-edge pixels full-size, half-size Turbo, six steps split 3+3. Custom
sizes and longer durations are accepted; zero duration means the rest of the
source. Longer clips require more VRAM, RAM and time. Whole clips are processed
in memory; unlimited duration is not a promise of unlimited memory.

Inputs/controls/results are persisted for the same browser/app address. A new
temporary public URL has separate browser site storage. Saved results remain
under jobs. Persistent progress and a Stop button show/control owned generation.

Uses Bernini-R FP8 HIGH/LOW, UMT5 FP8, Wan 2.1 BF16 VAE, and the workflow's
LightX2V speed adapter. Pinned models total about 36.1 GiB. Windows 64-bit,
Python 3.11, NVIDIA GPU, CUDA-13-compatible driver; 24 GB development GPU.
No full ComfyUI installation or server is required. Selected inference core and
Bernini conditioning code are included with their upstream licenses.

See HANDOFF.md for what has actually been tested. Model quality and speed depend
on media and settings; do not treat a short smoke result as a universal benchmark.

## Install from source and update

Clone https://codeberg.org/Cognibuild/GGF-Bernini (or https://github.com/gjnave/GGF-Bernini). In Command Prompt, enter that folder and run:

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe download_models.py
.venv\Scripts\python.exe app.py
```

Use Settings → Check for updates → Update and restart, or run `.venv\Scripts\python.exe update_app.py` with the server closed. Updates use archives generated automatically from the current Codeberg/GitHub repository. No source ZIP is manually rebuilt. Git is not required for updates. Models, settings, jobs and results are preserved; replaced source is backed up.

## Attribution

[Bernini conditioning](https://github.com/RH-RunningHub/ComfyUI-RH-Bernini),
the [source workflow bundle](https://github.com/gjnave/bernini-comfy-standalone),
and [Comfy inference code](https://github.com/Comfy-Org/ComfyUI) retain their
respective notices and GPL licenses. Model weights retain separate licenses;
their source URLs, pinned revisions and hashes are in model_manifest.json.
