import pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app

class VideoBatchTests(unittest.TestCase):
    def test_visual_batch_limit(self):
        with self.assertRaises(ValueError):app.start_task({'prompt':'video','images':['data:image/jpeg;base64,AA==']*13})
        with self.assertRaises(ValueError):app.start_task({'prompt':'video','images':['https://example.com/x.jpg']})
    def test_every_batch_is_analyzed_and_recorded(self):
        class InlineThread:
            def __init__(self,target,**kwargs):self.target=target
            def start(self):self.target()
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DATA',pathlib.Path(directory)),patch.dict(app.TASKS,{},clear=True),patch('threading.Thread',InlineThread),patch('providers.provider'),patch('evolution.active',return_value=''),patch('app.vision',side_effect=['first observation','second observation']) as vision,patch('app.run'):
            result=app.start_task({'prompt':'Compare timeline','images':['data:image/jpeg;base64,AA==']*2})
            task=app.TASKS[result['id']]
            self.assertEqual(vision.call_count,2);self.assertEqual(task['visual_batches'],2)
            self.assertIn('second observation',task['messages'][-1]['content'])
            self.assertFalse(task['input_pending'])
