"""GGF Bernini: edit a video using a prompt and optional reference image."""
import base64
import html
import json
import math
import os
import time
import uuid
from pathlib import Path
import gradio as gr
from config import ROOT,model_status,require_models
from media import inspect_video,output_canvas,SHAPES
import runtime
import workspace
from network_settings import read_settings,save_settings,verify_login,launch_access_servers,install_upload_disconnect_handling

VERSION=(ROOT/'VERSION').read_text().strip()
CSS=(ROOT/'style.css').read_text()
THEME=gr.themes.Base(primary_hue='amber',neutral_hue='slate').set(
    body_background_fill='#07101f',body_background_fill_dark='#07101f',
    body_text_color='#e8eef9',body_text_color_dark='#e8eef9',
    body_text_color_subdued='#b5c6dc',body_text_color_subdued_dark='#b5c6dc',
    block_background_fill='#111c2f',block_background_fill_dark='#111c2f',
    block_label_background_fill='#111c2f',block_label_background_fill_dark='#111c2f',
    block_label_text_color='#e8eef9',block_label_text_color_dark='#e8eef9',
    input_background_fill='#091425',input_background_fill_dark='#091425')
LOGO=base64.b64encode((ROOT/'assets'/'ggf-brain-logo.png').read_bytes()).decode()
HEADER=f'''<div class="ggf-hero"><div><div class="ggf-eyebrow">GET GOING FAST · LOCAL AI</div>
<h1>GGF Bernini</h1><p>Reshape your video. Keep the performance.</p>
<div class="ggf-links"><a href="https://getgoingfast.pro" target="_blank">GetGoingFast.pro ↗</a><a href="https://youtube.com/@TheAIHobbyGuy" target="_blank">The AI Hobby Guy ↗</a></div></div>
<img src="data:image/png;base64,{LOGO}" alt="Get Going Fast"></div>'''
KEYS=['video','reference','prompt','start','duration','size','shape','seed','steps','split','ref_size','high_lora','low_lora','negative']
DEFAULTS=[None,None,'',0,3,480,'Match uploaded video',-1,6,3,640,3.,1.5,'bad video']
ACTIVE_URLS={}

def restore(token):
    owner=token if workspace.valid_owner(token) else uuid.uuid4().hex
    saved=workspace.load(owner)
    form=saved.get('form',{})
    values=[form.get(k,d) for k,d in zip(KEYS,DEFAULTS)]
    for index in [0,1]:
        if values[index] and not Path(values[index]).is_file(): values[index]=None
    if values[6] not in ['Match uploaded video',*SHAPES]: values[6]='Match uploaded video'
    state={'owner':owner,'output':saved.get('output')}
    return [owner,state,*values,saved.get('output'),saved.get('status','Upload a video, describe the edit, and generate.')]

def remember(state,*values):
    if not state: return
    form=dict(zip(KEYS,values))
    for key in ['video','reference']: form[key]=workspace.keep_file(state['owner'],form[key])
    workspace.save(state['owner'],form=form)

def dimensions(video,start,duration,size,shape):
    if not video: return 'Upload a video to detect its orientation and output size.'
    try:
        meta=inspect_video(video)
        w,h=output_canvas(meta,float(size),shape)
        seconds=min(float(duration) or meta['duration'],max(0,meta['duration']-float(start)))
        return f"Input {meta['width']} × {meta['height']} · {meta['duration']:.1f}s. Output {w} × {h} · up to {seconds:.1f}s. Original audio retained."
    except Exception as error: return str(error)

def edit(state,*values,turbo=False,progress=gr.Progress()):
    if not state: raise gr.Error('The app is still loading. Try again in a moment.')
    form=dict(zip(KEYS,values))
    if not form['video']: raise gr.Error('Upload a video and wait for its preview first.')
    for name in ['start','duration','size','steps','split','ref_size','seed','high_lora','low_lora']:
        if not math.isfinite(float(form[name])): raise gr.Error(name+' must be a finite number.')
    if float(form['duration'])<0 or float(form['size'])<32 or int(form['steps'])<2 or int(form['ref_size'])<16:
        raise gr.Error('Use a nonnegative duration, at least 32 pixels, at least two steps, and a reference size of at least 16.')
    try:
        require_models()
        meta=inspect_video(form['video'])
        if not 0<=float(form['start'])<meta['duration']: raise ValueError('Start time must be inside the video.')
        remember(state,*values)
        saved=workspace.load(state['owner'])['form']
        request={**form,'video':saved['video'],'reference':saved['reference'],'mode':'video'}
        request['size']=max(32,round(float(form['size'])/2/32)*32) if turbo else int(form['size'])
    except Exception as error: raise gr.Error(str(error)) from None
    yield None,'Starting Bernini…'
    try:
        result=runtime.generate(request,state['owner'],lambda message:progress(0,desc=message))
    except Exception as error:
        workspace.save(state['owner'],status=str(error))
        raise gr.Error(str(error)) from None
    message=f"Finished in {result['seconds']:.1f}s · {result['width']} × {result['height']} · {result['frames']} frames · seed {result['seed']} · peak GPU {result['peak_vram_gib']:.1f} GB."
    workspace.save(state['owner'],output=result['output'],status=message)
    yield result['output'],message

def turbo_edit(state,*values,progress=gr.Progress()):
    yield from edit(state,*values,turbo=True,progress=progress)

def activity(state):
    if not state: return '',gr.skip(),gr.skip(),gr.skip(),gr.skip(),gr.skip()
    saved=workspace.load(state['owner'])
    value=saved.get('activity')
    banner=''
    running=False
    if value:
        running=value.get('running',False)
        if running and not runtime.LOCK.locked():
            value.update(running=False,error=True,finished=time.time(),stage='The server stopped before this generation finished.')
            workspace.save(state['owner'],activity=value)
            running=False
        elapsed=max(0,int((time.time() if running else value.get('finished',time.time()))-value['started']))
        title='GENERATING VIDEO' if running else 'GENERATION STOPPED' if value.get('error') else 'GENERATION COMPLETE'
        kind='running' if running else 'stopped' if value.get('error') else 'complete'
        banner=f'<div class="generation-banner {kind}" role="status"><strong>{title} · {elapsed//60}:{elapsed%60:02d}</strong><div>{html.escape(value["stage"])}</div></div>'
    new_output=saved.get('output')
    if new_output!=state.get('output'):
        state={**state,'output':new_output}
        return banner,gr.update(interactive=not running),gr.update(interactive=not running),state,new_output,saved.get('status','')
    return banner,gr.update(interactive=not running),gr.update(interactive=not running),gr.skip(),gr.skip(),gr.skip()

def save_access(mode,username,password):
    labels={'This computer only':'local','Local network':'lan','Temporary public link':'public'}
    saved=save_settings(labels[mode],username,password)
    return 'Saved. Restart RUN.bat to apply. Local access stays login-free. '+('Remote login enabled.' if saved['digest'] else 'Remote login off. Anyone with the link can use the app.')

def build_demo():
    with gr.Blocks(title='GGF Bernini') as demo:
        state=gr.State(None)
        token=gr.Textbox('',visible=False)
        gr.HTML(HEADER)
        banner=gr.HTML('',elem_id='generation-activity')
        with gr.Tabs():
            with gr.Tab('Create',id='create'):
                gr.Markdown('Edit the scene, subject, clothing, or style using a video, an optional reference photo, and your instructions.')
                with gr.Row(equal_height=True,elem_id='input-media'):
                    video=gr.Video(label='Your video',sources=['upload'],height=340)
                    reference=gr.Image(label='Reference look · optional',sources=['upload','clipboard'],type='filepath',height=340)
                prompt=gr.Textbox(label='What should change? · optional',placeholder='Replace the person with the character in the reference photo. Keep the motion and background.',lines=3)
                with gr.Row():
                    start=gr.Number(label='Start (seconds)',value=0,minimum=0)
                    duration=gr.Number(label='Duration (seconds) · 0 = to end',value=3,minimum=0)
                with gr.Row():
                    size=gr.Dropdown([384,480,576,768],value=480,allow_custom_value=True,label='Output short edge (pixels)')
                    shape=gr.Dropdown(['Match uploaded video',*SHAPES],value='Match uploaded video',label='Shape',interactive=True)
                size_notice=gr.Markdown('Upload a video to detect its orientation and output size.')
                gr.Markdown('Turbo halves the selected dimensions. Start with a short clip; longer videos and larger images require more memory and time. There is no fixed duration cap.')
                turbo=gr.Button('Turbo preview · half size · Ctrl+Enter',variant='primary',elem_id='turbo-edit')
                render=gr.Button('Generate edit · full size',variant='primary')
                stop=gr.Button('Stop current generation',variant='secondary')
                status=gr.Markdown('Upload a video, describe the edit, and generate.',elem_id='job-status')
                output=gr.Video(label='Your edited video · original audio retained',height=560,interactive=False,format='mp4',elem_id='result-video')
                expand=gr.Button('Expand video / exit fullscreen',variant='secondary')
                expand.click(None,[],[],queue=False,js="""async()=>{const b=document.querySelector('#result-video'),v=b?.querySelector('video');if(!v)return;if(document.fullscreenElement){await document.exitFullscreen();return;}if(b.classList.contains('expanded-video')){b.classList.remove('expanded-video');return;}try{if(v.requestFullscreen){await v.requestFullscreen();return;}if(v.webkitEnterFullscreen){v.webkitEnterFullscreen();return;}}catch(e){}b.classList.add('expanded-video');}""")
            with gr.Tab('Settings',id='settings'):
                gr.Markdown(f'### GGF Bernini · {VERSION}')
                installed=gr.Textbox(label='Models',value=model_status,lines=5,interactive=False)
                refresh=gr.Button('Check model files',variant='secondary')
                gr.Markdown('### Generation settings')
                with gr.Row():
                    steps=gr.Number(label='Sampling steps',value=6,minimum=2,precision=0)
                    split=gr.Number(label='HIGH stage steps',value=3,minimum=1,precision=0)
                    seed=gr.Number(label='Seed · -1 = random',value=-1,precision=0)
                ref_size=gr.Number(label='Reference maximum long edge (pixels)',value=640,minimum=16,precision=0)
                with gr.Accordion('Advanced speed adapter settings',open=False):
                    high_lora=gr.Number(label='LightX2V HIGH strength',value=3.)
                    low_lora=gr.Number(label='LightX2V LOW strength',value=1.5)
                    negative=gr.Textbox(label='Negative prompt',value='bad video',lines=2)
                check=gr.Button('Check for updates',variant='secondary')
                install_update=gr.Button('Update and restart',variant='primary')
                update_notice=gr.Markdown('Run UPDATE.bat with the app closed to install updates. Models, settings, and results are kept.')
                gr.Markdown('### Use on your phone')
                saved=read_settings()
                modes={'local':'This computer only','lan':'Local network','public':'Temporary public link'}
                access=gr.Dropdown(list(modes.values()),value=modes[saved['mode']],label='Access mode',interactive=True)
                with gr.Row():
                    username=gr.Textbox(label='Username',value=saved['username'],placeholder='ggf')
                    password=gr.Textbox(label='Password · blank turns login off',type='password')
                save=gr.Button('Save access settings',variant='secondary')
                network_notice=gr.Markdown('Save and restart to apply. Local access always works without login. Public links are temporary and change after restart.')
                gr.Button('Show current app links',variant='secondary').click(lambda:'\n\n'.join(f'{k}: {v}' for k,v in ACTIVE_URLS.items() if v),outputs=network_notice,queue=False)
                save.click(save_access,[access,username,password],network_notice,queue=False)
                refresh.click(model_status,outputs=installed,queue=False)
                def check_updates():
                    from update_app import check_update
                    return check_update()
                check.click(check_updates,outputs=update_notice,queue=False)
                def update_and_restart():
                    import threading
                    from update_app import start_restart
                    if not runtime.LOCK.acquire(blocking=False):
                        return 'Finish or stop the current generation before updating.'
                    try:
                        start_restart()
                    except Exception as error:
                        runtime.LOCK.release()
                        return f'Update could not start: {error}'
                    timer=threading.Timer(3,lambda: os._exit(0))
                    timer.daemon=True
                    timer.start()
                    return 'Updating and restarting. The local app will reopen; temporary public phone links may change.'
                install_update.click(update_and_restart,outputs=update_notice,queue=False)
        gr.HTML(f'<div class="ggf-footer">Powered by Bernini-R / Wan 2.2 · app-local inference · {VERSION}<br>Your Time Is Limited. Get Going Fast.</div>')
        controls=[video,reference,prompt,start,duration,size,shape,seed,steps,split,ref_size,high_lora,low_lora,negative]
        for control in controls:
            control.input(remember,[state,*controls],[],queue=False,show_progress='hidden')
        for control in [video,start,duration,size,shape]:
            control.change(dimensions,[video,start,duration,size,shape],size_notice,queue=False,show_progress='hidden')
        turbo.click(turbo_edit,[state,*controls],[output,status],concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        render.click(edit,[state,*controls],[output,status],concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        stop.click(lambda s:runtime.cancel(s['owner']) if s else 'No running generation.',[state],status,queue=False)
        demo.load(restore,[token],[token,state,*controls,output,status],queue=False,show_progress='hidden',js="()=>{const k='ggf-bernini-workspace-v1';let t=localStorage.getItem(k);if(!/^[a-f0-9]{32}$/.test(t||'')){t=crypto.randomUUID().replaceAll('-','');localStorage.setItem(k,t);}return [t];}")
        demo.load(None,[],[],js="()=>{if(!window.ggfBerniniKeys){window.ggfBerniniKeys=true;document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();document.querySelector('#turbo-edit')?.click();}})}return [];}")
        gr.Timer(1).tick(activity,[state],[banner,render,turbo,state,output,status],queue=False,show_progress='hidden')
    demo.queue(max_size=4,default_concurrency_limit=1)
    return demo

if __name__=='__main__':
    (ROOT/'logs').mkdir(exist_ok=True)
    (ROOT/'app.lock').write_text(str(os.getpid()))
    install_upload_disconnect_handling()
    saved=read_settings()
    auth=(lambda u,p:verify_login(u,p,saved)) if saved['digest'] else None
    local,remote,local_url,remote_url=launch_access_servers(build_demo,mode=saved['mode'],preferred_port=int(os.environ.get('GGF_BERNINI_PORT','7864')),auth=auth,inbrowser='--no-browser' not in os.sys.argv,css=CSS,theme=THEME,allowed_paths=[str(ROOT/'jobs')],show_error=True,footer_links=[])
    ACTIVE_URLS.update(Local=local_url,Remote=remote_url)
    local.block_thread()
