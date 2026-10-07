import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import runtime
import workspace
from update_app import stage_archive,safe_name

class AppTests(unittest.TestCase):
    def test_vendor_models_module_is_safe_but_customer_models_are_private(self):
        self.assertTrue(safe_name('vendor/comfy_core/comfy/ldm/models/autoencoder.py'))
        self.assertFalse(safe_name('models/autoencoder.py'))
        self.assertFalse(safe_name('vendor/comfy_core/comfy/ldm/models/../../local_settings.json'))
    def test_workspace_restores_and_migrates_bad_shape(self):
        root=Path(tempfile.mkdtemp(prefix='bernini-test-'))
        owner='b'*32
        with patch.object(workspace,'BASE',root):
            workspace.save(owner,form={'prompt':'replace the hat','duration':65,'shape':'stale invalid value'},output=None)
            restored=app.restore(owner)
            self.assertEqual(restored[4],'replace the hat')
            self.assertEqual(restored[6],65)
            self.assertEqual(restored[8],'Match uploaded video')

    def test_progress_disconnect_does_not_abort_job(self):
        root=Path(tempfile.mkdtemp(prefix='bernini-runtime-test-'))
        owner='c'*32
        process=Mock()
        process.poll.return_value=0
        process.stdout=io.StringIO('__GGF__{"progress":"HIGH stage step 1"}\n__GGF__{"ok":true,"output":"new.mp4"}\n')
        callback=Mock(side_effect=ConnectionError('phone disconnected'))
        with patch.object(workspace,'BASE',root/'workspaces'),patch.object(runtime,'job_directory',return_value=root),patch.object(runtime.subprocess,'Popen',return_value=process):
            workspace.save(owner,output='previous.mp4')
            result=runtime.generate({'mode':'video'},owner,callback)
            self.assertTrue(result['ok'])
            self.assertFalse(runtime.LOCK.locked())
            saved=workspace.load(owner)
            self.assertIsNone(saved['output'])
            self.assertFalse(saved['activity']['running'])
            callback.assert_called_once()

    def test_turbo_request_halves_resolution_and_clears_display(self):
        values=list(app.DEFAULTS)
        values[0]='video.mp4'
        values[5]=480
        state={'owner':'d'*32,'output':'old.mp4'}
        result=dict(output='new.mp4',seconds=3,width=256,height=448,frames=24,seed=1,peak_vram_gib=20)
        captured=[]
        def generate(request,*args): captured.append(request); return result
        form=dict(zip(app.KEYS,values))
        with patch.object(app,'require_models'),patch.object(app,'inspect_video',return_value={'duration':10}),patch.object(app,'remember'),patch.object(workspace,'load',return_value={'form':form}),patch.object(workspace,'save'),patch.object(runtime,'generate',side_effect=generate):
            outputs=list(app.turbo_edit(state,*values))
        self.assertIsNone(outputs[0][0])
        self.assertEqual(captured[0]['size'],256)
        self.assertEqual(outputs[-1][0],'new.mp4')

if __name__=='__main__': unittest.main()
