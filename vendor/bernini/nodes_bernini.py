import torch
import re
from typing_extensions import override

import comfy.model_management
import comfy.utils
import node_helpers
from comfy_api.latest import ComfyExtension, io

from .prompt_enhancer import build_llm_prompt, build_prompt_request, get_system_prompt_for_task, parse_prompt_response


def _resize_long_edge(image, max_size, stride=16):
    """Resize (preserve aspect) so the long edge <= max_size, snapped to `stride`."""
    h, w = image.shape[1], image.shape[2]
    scale = min(max_size / max(h, w), 1.0)
    nh = max(stride, round(h * scale / stride) * stride)
    nw = max(stride, round(w * scale / stride) * stride)
    return comfy.utils.common_upscale(image[:, :, :, :3].movedim(-1, 1), nw, nh, "area", "disabled").movedim(1, -1)


def _scale_down_to_size(images, size, mode):
    h, w = images.shape[1], images.shape[2]
    size = max(int(size), 1)
    source_edge = max(h, w) if mode else min(h, w)
    if source_edge <= size:
        return images[:, :, :, :3]

    scale = size / source_edge
    height = max(1, round(h * scale))
    width = max(1, round(w * scale))
    return comfy.utils.common_upscale(images[:, :, :, :3].movedim(-1, 1), width, height, "area", "disabled").movedim(1, -1)


def _iter_reference_images(reference_images):
    if reference_images is None:
        return

    if isinstance(reference_images, (list, tuple)):
        for item in reference_images:
            yield from _iter_reference_images(item)
        return

    if hasattr(reference_images, "shape") and len(reference_images.shape) == 4:
        for i in range(reference_images.shape[0]):
            yield reference_images[i : i + 1]
        return

    yield reference_images


def _build_bernini_context(vae, length, width, height, source_video=None, reference_video=None, reference_images=None, ref_max_size=848):
    context = {}
    if source_video is not None:
        vid = comfy.utils.common_upscale(
            source_video[:length, :, :, :3].movedim(-1, 1), width, height, "area", "center"
        ).movedim(1, -1)
        context["video"] = vae.encode(vid[:, :, :, :3])

    refs = []
    if reference_video is not None:
        ref_vid = _resize_long_edge(reference_video[:length], ref_max_size)
        refs.append(vae.encode(ref_vid[:, :, :, :3]))

    for reference_image in _iter_reference_images(reference_images):
        img = _resize_long_edge(reference_image, ref_max_size)
        refs.append(vae.encode(img[:, :, :, :3]))

    context["refs"] = refs
    return context


def _build_chat_prompts(system_prompt, api_prompt, original_prompt):
    system_prompt = (system_prompt or "").strip()
    api_prompt = (api_prompt or "").strip()
    original_prompt = (original_prompt or "").strip()
    if not api_prompt or api_prompt == original_prompt:
        return system_prompt, original_prompt

    text = api_prompt
    match = re.search(
        r"\n\s*(?P<label>Original (?:instruction|description)):\s*\n(?P<user>.*?)\s*$",
        text,
        flags=re.DOTALL,
    )
    if match:
        return text[: match.start()].strip(), match.group("user").strip()

    match = re.search(
        r"(?m)^\s*-?\s*User's (?:raw instruction|editing instruction|instruction|prompt):\s*\"(?P<user>.*?)\"\s*$",
        text,
    )
    if match:
        cleaned = (text[: match.start()] + text[match.end() :]).strip()
        return cleaned, match.group("user").strip()

    return api_prompt, original_prompt


class EasyImageScaleDownToSizeCompat(io.ComfyNode):
    """Compatibility shim for old Bernini workflows saved with ComfyUI-Easy-Use."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="easy imageScaleDownToSize",
            display_name="Image Scale Down To Size",
            category="EasyUse/Image",
            inputs=[
                io.Image.Input("images"),
                io.Int.Input("size", default=512, min=1, max=8192, step=1),
                io.Boolean.Input("mode", default=True),
            ],
            outputs=[io.Image.Output(display_name="IMAGE")],
        )

    @classmethod
    def execute(cls, images, size=512, mode=True) -> io.NodeOutput:
        return io.NodeOutput(_scale_down_to_size(images, size, mode))


class BerniniConditioning(io.ComfyNode):
    """Bernini in-context conditioning for a Wan2.2-A14B model.

    Attaches the VAE-encoded source video / reference images to the conditioning
    an ordered list of clean latents (source video first, then each reference image),
    which the Wan model appends as extra tokens with per-stream source_id rope.

    The task is inferred from which inputs are connected:
    (nothing) -> t2v
    source_video -> v2v
    source_video + ref images -> rv2v
    ref images only -> r2v (each kept at native aspect)
    source_video + ref_video -> video insertion / "ads2v"

    source_video is the edit base / canvas (resized to width x height).
    reference_video is moving content to composite in (e.g. a clip to play on a
    screen), kept at its native aspect like the reference images. Streams are
    ordered source_video, reference_video, then reference_images -> source_id
    1, 2, 3... matching the reference repo's [base, content, refs].
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="BerniniConditioning",
            display_name="Bernini Conditioning",
            category="conditioning/video_models",
            description=(
                "Conditioning node for Bernini in-context video/image conditioning. "
                "Attach source video and/or reference images to the positive/negative conditioning, "
                "which the Wan model will append as extra tokens with per-stream source_id rope."
            ),
            inputs=[
                io.Conditioning.Input(
                    "positive",
                    tooltip="Positive conditioning from the Wan text encoder. The Bernini context latents are attached to this conditioning.",
                ),
                io.Conditioning.Input(
                    "negative",
                    tooltip="Negative conditioning from the Wan text encoder. The same Bernini context latents are attached for sampler compatibility.",
                ),
                io.Vae.Input("vae", tooltip="VAE used to encode source video and reference images into Wan latent space."),
                io.Int.Input(
                    "width",
                    default=832,
                    min=16,
                    max=8192,
                    step=16,
                    tooltip="Output latent width in pixels. Source video is resized to this width.",
                ),
                io.Int.Input(
                    "height",
                    default=480,
                    min=16,
                    max=8192,
                    step=16,
                    tooltip="Output latent height in pixels. Source video is resized to this height.",
                ),
                io.Int.Input(
                    "length",
                    default=81,
                    min=1,
                    max=8192,
                    step=4,
                    tooltip="Number of video frames to generate or condition. Source/reference videos are trimmed to this length.",
                ),
                io.Int.Input(
                    "batch_size",
                    default=1,
                    min=1,
                    max=4096,
                    tooltip="Number of latent samples to create for sampling.",
                ),
                io.Image.Input(
                    "source_video",
                    optional=True,
                    tooltip=(
                        "Source video to edit/restyle (task v2v or rv2v). "
                        "Resized to width/height and trimmed to length. Acts as the edit base / canvas."
                    ),
                ),
                io.Image.Input(
                    "reference_video",
                    optional=True,
                    tooltip=(
                        "Moving content to composite into the source video (video insertion / ads2v), "
                        "e.g. a clip to play on a screen. Kept at native aspect (long edge capped at ref_max_size), "
                        "trimmed to length."
                    ),
                ),
                io.Image.Input(
                    "reference_images",
                    optional=True,
                    tooltip=(
                        "Reference image(s) injected as in-context tokens (task r2v or rv2v). "
                        "Each is kept at its native aspect ratio, long edge capped at ref_max_size."
                    ),
                ),
                io.Int.Input(
                    "ref_max_size",
                    default=848,
                    min=16,
                    max=8192,
                    step=16,
                    optional=True,
                    tooltip="Maximum long edge for reference video and reference images. References keep aspect ratio and are not upscaled.",
                ),
            ],
            outputs=[
                io.Conditioning.Output(display_name="positive"),
                io.Conditioning.Output(display_name="negative"),
                io.Latent.Output(display_name="latent"),
            ],
        )

    @classmethod
    def execute(
        cls,
        positive,
        negative,
        vae,
        width,
        height,
        length,
        batch_size,
        source_video=None,
        reference_video=None,
        reference_images=None,
        ref_max_size=848,
        **kwargs,
    ) -> io.NodeOutput:
        expanded_reference_images = [
            value
            for key, value in sorted(kwargs.items())
            if key.startswith("reference_images.") and value is not None
        ]
        if expanded_reference_images:
            if reference_images is None:
                reference_images = expanded_reference_images
            elif isinstance(reference_images, list):
                reference_images.extend(expanded_reference_images)
            else:
                reference_images = [reference_images, *expanded_reference_images]

        latent = torch.zeros(
            [batch_size, 16, ((length - 1) // 4) + 1, height // 8, width // 8],
            device=comfy.model_management.intermediate_device(),
        )

        context_parts = _build_bernini_context(
            vae,
            length,
            width,
            height,
            source_video=source_video,
            reference_video=reference_video,
            reference_images=reference_images,
            ref_max_size=ref_max_size,
        )
        context = []
        if "video" in context_parts:
            context.append(context_parts["video"])
        context.extend(context_parts["refs"])

        if context:
            positive = node_helpers.conditioning_set_values(positive, {"context_latents": context})
            negative = node_helpers.conditioning_set_values(negative, {"context_latents": context})

        return io.NodeOutput(positive, negative, {"samples": latent})


class BerniniPromptEnhancer(io.ComfyNode):
    """Build the official Bernini prompt-enhancement request for external API nodes."""

    TASK_TYPES = [
        "t2v",
        "t2i",
        "v2v",
        "mv2v",
        "i2i",
        "i2v",
        "r2v",
        "r2i",
        "rv2v",
        "vrc2v",
        "vi2v",
        "ads2v",
    ]

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="BerniniPromptEnhancer",
            display_name="Bernini Prompt Enhancer",
            category="conditioning/video_models",
            description=(
                "Build the official task-aware Bernini prompt-enhancement instructions. "
                "Connect system_prompt and user_prompt to an external LLM node, then parse its response."
            ),
            inputs=[
                io.String.Input(
                    "prompt",
                    multiline=True,
                    default="",
                    placeholder="Original Bernini prompt",
                    tooltip="Original user instruction or generation prompt. For Chinese input, the enhancer asks the external LLM to rewrite it in English.",
                ),
                io.Combo.Input(
                    "task_type",
                    options=cls.TASK_TYPES,
                    default="v2v",
                    tooltip="Bernini task type. Choose the mode that matches connected media and the intended generation or editing workflow.",
                ),
                io.Int.Input(
                    "video_frames",
                    default=3,
                    min=1,
                    max=8,
                    advanced=True,
                    tooltip="Number of source video frames described to the external vision LLM in prompt-enhancement tasks.",
                ),
                io.Image.Input(
                    "source_video",
                    optional=True,
                    tooltip=(
                        "Optional source video frames. Also connect the same frames to your external vision API node "
                        "when the selected task needs visual context."
                    ),
                ),
                io.Image.Input(
                    "source_image",
                    optional=True,
                    tooltip="Optional source image. Also connect it to your external vision API node for i2i/i2v tasks.",
                ),
                io.Image.Input(
                    "reference_images",
                    optional=True,
                    tooltip=(
                        "Optional reference image batch. Also connect it to your external vision API node for "
                        "r2v/r2i/rv2v/vrc2v/vi2v tasks."
                    ),
                ),
            ],
            outputs=[
                io.String.Output(display_name="system_prompt"),
                io.String.Output(display_name="user_prompt"),
                io.String.Output(display_name="llm_prompt"),
                io.String.Output(display_name="api_prompt"),
                io.String.Output(display_name="json_mode"),
            ],
        )

    @classmethod
    def execute(
        cls,
        prompt,
        task_type,
        video_frames=3,
        source_video=None,
        source_image=None,
        reference_images=None,
    ) -> io.NodeOutput:
        prompt = (prompt or "").strip()
        if not prompt:
            system_prompt = get_system_prompt_for_task(task_type)
            return io.NodeOutput(system_prompt, "", "", "", "false")

        system_prompt, api_prompt, json_mode = build_prompt_request(
            task_type,
            prompt,
            video=source_video,
            image=source_image,
            images=reference_images,
            video_frames=video_frames,
        )
        chat_system_prompt, chat_user_prompt = _build_chat_prompts(system_prompt, api_prompt, prompt)
        llm_prompt = build_llm_prompt(chat_system_prompt, chat_user_prompt, json_mode=json_mode)
        return io.NodeOutput(
            chat_system_prompt,
            chat_user_prompt,
            llm_prompt,
            api_prompt,
            "true" if json_mode else "false",
        )


class BerniniPromptResultParser(io.ComfyNode):
    """Parse an external API node response into the final enhanced Bernini prompt."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="BerniniPromptResultParser",
            display_name="Bernini Prompt Result Parser",
            category="conditioning/video_models",
            description="Parse the response from an external API node into a final Bernini prompt.",
            inputs=[
                io.String.Input(
                    "api_response",
                    multiline=True,
                    default="",
                    force_input=True,
                    tooltip="Raw text returned by the external LLM node. JSON responses are supported when json_mode is true.",
                ),
                io.String.Input(
                    "original_prompt",
                    multiline=True,
                    default="",
                    advanced=True,
                    tooltip="Fallback prompt returned when the external LLM response is empty.",
                ),
                io.String.Input(
                    "json_mode",
                    default="false",
                    advanced=True,
                    tooltip="Set to true when the external LLM is expected to return a JSON object containing rewritten_text.",
                ),
            ],
            outputs=[
                io.String.Output(display_name="enhanced_prompt"),
            ],
        )

    @classmethod
    def execute(cls, api_response, original_prompt="", json_mode="false") -> io.NodeOutput:
        json_mode = str(json_mode or "").strip().lower() in {"1", "true", "yes", "json"}
        return io.NodeOutput(parse_prompt_response(api_response, original_prompt, json_mode=json_mode))


class BerniniExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            EasyImageScaleDownToSizeCompat,
            BerniniConditioning,
            BerniniPromptEnhancer,
            BerniniPromptResultParser,
        ]


async def comfy_entrypoint() -> BerniniExtension:
    return BerniniExtension()
