import importlib.util,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app,features,extension_tools,providers,evolution

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.work=pathlib.Path(self.tmp.name)/'workspace';self.data=pathlib.Path(self.tmp.name)/'data';self.work.mkdir();self.data.mkdir()
        self.original=(app.WORK,app.DATA,features.WORK,features.DATA)
        app.WORK=features.WORK=self.work;app.DATA=features.DATA=self.data
    def tearDown(self):
        app.WORK,app.DATA,features.WORK,features.DATA=self.original;self.tmp.cleanup()
    def test_path_boundary(self):
        for name in ('../secret.txt',str(self.data/'secret')):
            with self.assertRaises(ValueError):app.safe_path(name)
        self.assertEqual(app.safe_path('notes.txt'),self.work/'notes.txt')
    def test_file_backup(self):
        app.tool('write_file',{'path':'a.txt','content':'old'})
        result=app.tool('write_file',{'path':'a.txt','content':'new'})
        self.assertEqual(pathlib.Path(result['backup']).read_text(),'old')
        self.assertEqual(app.tool('read_file',{'path':'a.txt'}),'new')
    def test_edit_unique_match(self):
        p=self.work/'code.py';p.write_text('return 1\n')
        old,new,diff=features.edit_patch(p,'1','2')
        self.assertIn('+return 2',diff);self.assertEqual(p.read_text(),old)
        with self.assertRaises(ValueError):features.edit_patch(p,'missing','2')
    def test_pdf_and_docx(self):
        import pymupdf
        p=self.work/'paper.pdf';d=pymupdf.open();page=d.new_page();page.insert_text((50,50),'RAG uses retrieval to ground answers.');d.save(p);d.close()
        self.assertIn('retrieval',features.document(p)['text'])
        out=self.work/'notes.docx';features.make_docx(out,'Notes','## Method\nUse retrieval.')
        self.assertIn('Use retrieval',features.document(out)['text'])
    def test_hybrid_retrieval(self):
        # Deterministic vectors verify ranking and citations independently of model downloads.
        old=features.vectors
        features.vectors=lambda texts,query=False:[[1.,0.] if 'RAG' in t else [0.,1.] for t in texts]
        try:
            p=self.work/'rag.txt';p.write_text('RAG retrieves documents before answering.')
            self.assertEqual(features.index(p)['chunks'],1)
            self.assertTrue(features.index(p)['cached'])
            r=features.search('RAG')[0];self.assertEqual(r['page'],1);self.assertIn('rag.txt',r['citation'])
        finally:features.vectors=old
    def test_feedback_export_dedup(self):
        features.feedback('task1',1,'Correct answer')
        features.feedback('task1',1,'Correct answer')
        r=features.export_training({'task1':{'messages':[{'role':'user','content':'Question'}],'answer':'Wrong answer'}})
        self.assertEqual(r['samples'],1)
        files=list(pathlib.Path(r['directory']).glob('*.jsonl'))
        self.assertEqual(sum(len(p.read_text().splitlines()) for p in files),1)
    def test_evolution_gate(self):
        p=evolution.create('Be precise.')
        with features.database() as c:c.execute('INSERT INTO evaluations VALUES(?,?,?)',('bad',json.dumps({'profile':p['id'],'eligible':False}),0))
        with self.assertRaises(ValueError):evolution.activate(p['id'],'bad')
        self.assertEqual(evolution.active(),'')
    def test_tool_groups(self):
        groups=extension_tools.groups_for('读取PDF论文并检索知识库')
        self.assertIn('documents',groups);self.assertIn('knowledge',groups)
        names=[x['function']['name'] for x in extension_tools.schemas(groups)]
        self.assertIn('read_document',names);self.assertNotIn('desktop_click',names)
    def test_remote_requires_secure_transport(self):
        old=providers.config;providers.config=lambda:{'remote':{'base_url':'http://example.com/v1','model':'x'}}
        try:
            with self.assertRaises(ValueError):providers.provider('remote')
        finally:providers.config=old
    def test_context_keeps_tool_pairs(self):
        messages=[{'role':'system','content':'system'},{'role':'user','content':'goal'}]
        for i in range(10):messages.extend([{'role':'assistant','tool_calls':[{'id':str(i)}]},{'role':'tool','tool_call_id':str(i),'content':'x'*2000}])
        out=providers.compact(messages,[])
        ids={c['id'] for m in out for c in m.get('tool_calls',[])}
        self.assertTrue(all(m.get('tool_call_id') in ids for m in out if m['role']=='tool'))
    def test_context_preserves_latest_goal(self):
        messages=[{'role':'system','content':'system'},{'role':'user','content':'old goal'},{'role':'assistant','content':'x'*12000},{'role':'user','content':'new goal'}]
        out=providers.compact(messages,[])
        self.assertEqual(next(m['content'] for m in out if m['role']=='user'),'new goal')
    def test_calculator_no_code_execution(self):
        self.assertEqual(app.tool('calculate',{'expression':'17*23'})['result'],391)
        with self.assertRaises(ValueError):app.tool('calculate',{'expression':"__import__('os').getcwd()"})
        with self.assertRaises(ValueError):app.tool('calculate',{'expression':'2**99999'})

if __name__=='__main__':unittest.main()
