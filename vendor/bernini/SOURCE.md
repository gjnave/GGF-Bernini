# Bernini conditioning and compatibility patch

Copied from gjnave/bernini-comfy-standalone commit
8576165db4c39e1c6bd6cc48591c049a8170d2c5, custom_nodes/ComfyUI-RH-Bernini.
Original project: RH-RunningHub/ComfyUI-RH-Bernini, author flybirdxx.
Retains the upstream GPL-3.0-only license. The embedded Comfy core already
supports context_latents; the upstream compatibility patch recognizes that.
No custom-node discovery or external prompt-enhancement API is used by this app.
