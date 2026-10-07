"""Media helpers: exact frame capture and original-audio preservation."""
import json
import math
import subprocess
import shutil
from pathlib import Path
import av
import numpy as np
from PIL import Image

def ffmpeg():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def inspect_video(path):
    if not path or not Path(path).is_file():
        raise ValueError('Upload a video and wait for its preview first.')
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else (container.duration or 0) / 1e6
        if duration <= 0:
            raise ValueError('Could not determine video duration. Try an MP4 export.')
        first = next(container.decode(stream), None)
        rotation = int(first.rotation or 0) if first is not None else 0
        width, height = stream.width, stream.height
        if abs(rotation) % 180 == 90:
            width, height = height, width
        return dict(duration=duration, width=width, height=height, rotation=rotation,
                    fps=float(stream.average_rate or 24), audio=bool(container.streams.audio))

def capture_frame(path, seconds, destination):
    meta = inspect_video(path)
    seconds = min(max(0, float(seconds)), max(0, meta['duration'] - 1 / meta['fps']))
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        container.seek(int(seconds / stream.time_base), stream=stream, backward=True)
        chosen = None
        for frame in container.decode(stream):
            if frame.time is not None and frame.time >= seconds:
                if chosen is None or chosen.time is None or abs(frame.time-seconds) < abs(chosen.time-seconds):
                    chosen = frame
                break
            chosen = frame
        if chosen is None:
            raise ValueError('That frame could not be decoded. Choose an earlier time.')
        image = chosen.to_image()
        if meta.get('rotation'):
            image = image.rotate(meta['rotation'], expand=True)
        image.save(destination)
    return str(destination), float(chosen.time) if chosen.time is not None else seconds, meta

def canvas(width, height, short_edge):
    scale = float(short_edge) / min(width, height)
    return max(32, round(width * scale / 32) * 32), max(32, round(height * scale / 32) * 32)

SHAPES = {'Portrait · 9:16':(9,16), 'Landscape · 16:9':(16,9), 'Square · 1:1':(1,1)}

def output_canvas(meta, short_edge, shape='Match uploaded video'):
    width, height = SHAPES.get(shape,(meta['width'],meta['height']))
    return canvas(width,height,short_edge)

def prepare_clip(source, start, duration, short_edge, destination, shape='Match uploaded video'):
    meta = inspect_video(source)
    start = float(start)
    if not math.isfinite(start) or start < 0 or start >= meta['duration']:
        raise ValueError('Start time must fall inside the source video.')
    duration = float(duration)
    if not math.isfinite(duration) or duration < 0:
        raise ValueError('Duration must be positive, or zero for the rest of the video.')
    length = min(duration or meta['duration'], meta['duration'] - start)
    width, height = output_canvas(meta, short_edge, shape)
    scale = f'scale={width}:{height}:flags=lanczos'
    if shape in SHAPES:
        scale += f':force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black'
    args = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-n', '-ss', str(start), '-i', str(source),
            '-t', str(length), '-map', '0:v:0', '-vf', f'fps=24,{scale},setsar=1',
            '-an', '-c:v', 'ffv1', '-pix_fmt', 'rgb24', str(destination)]
    subprocess.run(args, check=True, capture_output=True)
    return width, height, length

def load_frames(path):
    with av.open(str(path)) as container:
        frames = [f.to_ndarray(format='rgb24') for f in container.decode(video=0)]
    if not frames:
        raise ValueError('No video frames were decoded.')
    return np.stack(frames)

def save_video(frames, output, original, start, length, silent_path):
    height, width = frames.shape[1:3]
    with av.open(str(silent_path), 'w') as container:
        stream = container.add_stream('libx264', rate=24)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'fast'}
        for array in frames:
            array = (array.clip(0, 1) * 255).astype(np.uint8)
            frame = av.VideoFrame.from_ndarray(array, format='rgb24')
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-n', '-i', str(silent_path),
                    '-ss', str(start), '-i', str(original), '-map', '0:v:0', '-map', '1:a:0?',
                    '-t', str(length), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-metadata', 'comment=AI-generated likeness transfer | Get Going Fast',
                    '-movflags', '+faststart', str(output)], check=True, capture_output=True)
    return str(output)
