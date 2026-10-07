"""Bernini direct core inference. No ComfyUI application/server dependency."""
import json
import math
import random
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from config import ROOT,CORE

PROTOCOL=sys.stdout
def progress(message):
    PROTOCOL.write('__GGF__'+json.dumps({'progress':str(message)})+'\n')
    PROTOCOL.flush()

def run(request):
    started=time.perf_counter()
    attention=request.get('attention','sdpa')
    sys.argv=[sys.argv[0],'--reserve-vram','3','--preview-method','none']
    if attention=='sage': sys.argv.append('--use-sage-attention')
    else: sys.argv.append('--use-pytorch-cross-attention')
    sys.path.insert(0,str(CORE))
    import numpy as np
    import torch
    import nodes
    import folder_paths
    import comfy.model_management as mm
    import comfy.samplers
    import comfy.sample
    from comfy_extras.nodes_custom_sampler import BasicScheduler
    from vendor.bernini.nodes_bernini import BerniniConditioning
    from media import prepare_clip,load_frames,save_video
    from PIL import Image,ImageOps
    if not torch.cuda.is_available(): raise RuntimeError('CUDA is unavailable. Run INSTALL.bat with an NVIDIA GPU and current driver.')
    torch.cuda.reset_peak_memory_stats()
    model_root=Path(request['models'])
    for kind in ['diffusion_models','text_encoders','vae','loras']:
        folder_paths.add_model_folder_path(kind,str(model_root/kind),is_default=True)
    job=Path(request['job'])
    seed=int(request['seed'])
    if seed<0: seed=random.randrange(2**63)
    steps=int(request['steps'])
    split=max(1,min(steps-1,int(request['split'])))
    fps=24
    progress('Preparing the selected video range')
    width,height,length=prepare_clip(request['video'],request['start'],request['duration'],request['size'],job/'source.mkv',request['shape'])
    array=load_frames(job/'source.mkv')
    # Wan's temporal compression is 4n+1. Extend edge frames and trim output again.
    original_count=len(array)
    frames=1+math.ceil((original_count-1)/4)*4
    if frames>original_count: array=np.concatenate([array,np.repeat(array[-1:],frames-original_count,axis=0)])
    source=torch.from_numpy(array.copy()).float().div_(255)
    del array
    reference=None
    if request.get('reference'):
        image=ImageOps.exif_transpose(Image.open(request['reference'])).convert('RGB')
        image.thumbnail((request['ref_size'],request['ref_size']),Image.Resampling.LANCZOS)
        reference=torch.from_numpy(np.asarray(image).copy()).float().div_(255).unsqueeze(0)
    progress('Loading the text encoder and encoding your edit')
    clip=nodes.CLIPLoader().load_clip('umt5_xxl_fp8_e4m3fn_scaled.safetensors','wan','default')[0]
    direction=request['prompt'].strip() or ('Replace the main subject with the person or character in the reference image. Preserve the source action, camera movement, lighting, and background.' if reference is not None else 'Preserve the source video appearance and motion with natural, coherent details.')
    text='You are a helpful assistant specialized in video editing'+(' with reference. ' if reference is not None else '. ')+direction
    with torch.no_grad():
        positive=nodes.CLIPTextEncode().encode(clip,text)[0]
        negative=nodes.CLIPTextEncode().encode(clip,request['negative'])[0]
        del clip
        mm.unload_all_models()
        progress('Encoding the source video and reference image')
        vae=nodes.VAELoader().load_vae('Wan2_1_VAE_bf16.safetensors')[0]
        positive,negative,latent=BerniniConditioning.execute(positive,negative,vae,width,height,frames,1,source_video=source,reference_images=reference,ref_max_size=int(request['ref_size']))
        del source,reference
        mm.unload_all_models()
        sampler=comfy.samplers.sampler_object('res_multistep')
        progress('Loading the HIGH stage model')
        high=nodes.UNETLoader().load_unet('Bernini_HIGH_fp8_e4m3fn_scaled.safetensors','default')[0]
        high=nodes.LoraLoaderModelOnly().load_lora_model_only(high,'lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',float(request['high_lora']))[0]
        sigmas=BasicScheduler.execute(high,'simple',steps,1.)[0]
        noise=comfy.sample.prepare_noise(latent['samples'],seed)
        def sample(model,noise,sigma,samples,stage,offset):
            def callback(step,x0,x,total): progress(f'{stage} · step {offset+step+1} of {steps}')
            return comfy.sample.sample_custom(model,noise,1.,sampler,sigma,positive,negative,samples,callback=callback,disable_pbar=False,seed=seed)
        result=sample(high,noise,sigmas[:split+1],latent['samples'],'HIGH stage',0)
        del high,noise
        mm.unload_all_models()
        mm.soft_empty_cache()
        progress('Loading the LOW stage model')
        low=nodes.UNETLoader().load_unet('Bernini_LOW_fp8_e4m3fn_scaled.safetensors','default')[0]
        low=nodes.LoraLoaderModelOnly().load_lora_model_only(low,'lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',float(request['low_lora']))[0]
        result=sample(low,torch.zeros_like(result),sigmas[split:],result,'LOW stage',split)
        del low,positive,negative,latent
        mm.unload_all_models()
        mm.soft_empty_cache()
        progress('Decoding your video')
        pixels=vae.decode(result)
        # Wan decode returns B,T,H,W,C in this core; MP4 encoding needs T,H,W,C.
        if pixels.ndim==5: pixels=pixels[0]
        pixels=pixels[:original_count]
        del result
        progress('Saving your video and retaining original audio')
        output=job/f'GGF-Bernini-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:10]}.mp4'
        save_video(pixels.cpu().numpy(),output,request['video'],request['start'],length,job/'silent.mp4')
    return dict(output=str(output),seconds=round(time.perf_counter()-started,2),width=width,height=height,frames=original_count,seed=seed,peak_vram_gib=round(torch.cuda.max_memory_allocated()/2**30,2))

if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text())
    sys.stdout=sys.stderr
    try: result={'ok':True,**run(request)}
    except Exception as error:
        traceback.print_exc()
        message=str(error)
        if 'out of memory' in message.lower(): message='Memory ran out. Try Turbo, a shorter clip, or a smaller reference image. Your uploaded inputs and saved outputs are kept.'
        result={'ok':False,'error':message}
    PROTOCOL.write('__GGF__'+json.dumps(result)+'\n')
    PROTOCOL.flush()
