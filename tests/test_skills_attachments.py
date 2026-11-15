import pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app,skill_library

class AttachmentTests(unittest.TestCase):
    def test_reject_external_path_before_launch(self):
        with self.assertRaises(ValueError):app.start_task({'prompt':'read','attachments':['../outside.txt']})
    def test_unknown_skill(self):
        with self.assertRaises(ValueError):app.start_task({'prompt':'read','skills':['../../untrusted']})
    def test_attachment_evidence_and_skill_instructions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);(root/'paper.txt').write_text('evidence')
            with patch.object(app,'WORK',root),patch.object(app,'DATA',root),patch.object(app.providers,'provider'),patch.object(app.evolution,'active',return_value=''),patch.object(app.threading,'Thread'):
                result=app.start_task({'prompt':'read paper','attachments':['paper.txt'],'skills':['paper-review']})
                task=app.TASKS.pop(result['id'])
                self.assertEqual(task['attachments'][0]['bytes'],8)
                self.assertEqual(len(task['attachments'][0]['sha256']),64)
                self.assertIn('不能把训练集成绩',task['messages'][0]['content'])
                self.assertEqual(task['skills'][0]['id'],'paper-review')
                self.assertIn('documents',task['groups'])
    def test_bundled_catalog(self):
        self.assertEqual(len(skill_library.catalog()),3)
        self.assertEqual(len(skill_library.select(['code-change','code-change'])),1)
