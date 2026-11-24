import json,tempfile,unittest
from pathlib import Path
from routeocr.model import empty_tables,add_operation,validate_relations
from routeocr.__main__ import export,evaluate
from argparse import Namespace


def cell(text):return dict(text=text,confidence=.99)
class Relations(unittest.TestCase):
    def base(self):
        t=empty_tables();t['processes'].append(dict(id='TP'));return t
    def test_multiple_documents_per_equipment(self):
        t=self.base();add_operation(t,'TP',1,1,{'number':cell('001')},
            [dict(cell=cell('crane')),dict(cell=cell('slings'))],
            [dict(cell=cell('D1'),resource_indices=[1]),dict(cell=cell('D2'),resource_indices=[1,2])])
        validate_relations(t);self.assertEqual(len(t['resource_documents']),3)
        self.assertEqual(t['operations'][0]['number'],'001')
    def test_no_invented_associations(self):
        t=self.base();add_operation(t,'TP',1,1,{},[dict(cell=cell('A')),dict(cell=cell('B'))],[dict(cell=cell('D'))])
        self.assertFalse(t['resource_documents']);self.assertTrue(t['review'])
    def test_continuation_does_not_duplicate_operation(self):
        t=self.base();add_operation(t,'TP',1,1,{'number':cell('001')},[],[])
        add_operation(t,'TP',2,1,{},[dict(cell=cell('B'))],[dict(cell=cell('D'),resource_indices=[1])],continuation_of='p1/o1')
        validate_relations(t);self.assertEqual(len(t['operations']),1);self.assertEqual(len(t['resources']),1)
        self.assertEqual(t['operations'][0]['continuation_pages'],[2])
    def test_bad_index_rejected(self):
        with self.assertRaises(ValueError):add_operation(self.base(),'TP',1,1,{},[],[dict(cell=cell('D'),resource_indices=[1])])
    def test_export_preserves_ids_and_formula_text(self):
        import openpyxl
        t=self.base();add_operation(t,'TP',1,1,{'number':cell('001'),'content':cell('=1+1')},[],[])
        with tempfile.TemporaryDirectory() as d:
            export(t,Path(d));w=openpyxl.load_workbook(Path(d)/'tables.xlsx');s=w['operations'];keys=[c.value for c in s[1]]
            self.assertEqual(s.cell(2,keys.index('number')+1).value,'001')
            c=s.cell(2,keys.index('content')+1);self.assertEqual(c.value,'=1+1');self.assertEqual(c.data_type,'s')
    def test_cell_metrics_include_empty_reference_insertions(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'p').write_text(json.dumps([dict(key='a',text='abc'),dict(key='b',text='x')]))
            (d/'r').write_text(json.dumps([dict(key='a',text='abc',verified=True),dict(key='b',text='',verified=True)]))
            evaluate(Namespace(prediction=d/'p',reference=d/'r',output=d/'o',relaxed=False))
            m=json.loads((d/'o').read_text());self.assertAlmostEqual(m['cer'],1/3);self.assertEqual(m['exact_cell_accuracy'],.5)
