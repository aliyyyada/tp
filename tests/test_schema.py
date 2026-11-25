import unittest
from routeocr.model import empty_tables,add_operation
from routeocr.schema import public_tables
from tests.test_relations import cell
class PublicSchema(unittest.TestCase):
    def test_three_entities_and_distinct_document_meanings(self):
        t=empty_tables();t['processes'].append(dict(id='TP1',document_number='TP-123'))
        add_operation(t,'TP1',1,1,{'number':cell('001')},[dict(cell=cell('Crane')),dict(cell=cell('Slings'))],
            [dict(cell=cell('60205.00033'),resource_indices=[1]),dict(cell=cell('STD-1'),resource_indices=[1,2])])
        result=public_tables(t)
        self.assertEqual(set(result),{'documents','operations','equipment'})
        op=result['operations'][0];self.assertEqual(op['document_id'],'TP1');self.assertEqual(op['document'],'60205.00033\nSTD-1')
        self.assertEqual(len(result['equipment']),2);self.assertEqual(result['equipment'][0]['documents'],['60205.00033','STD-1'])
        self.assertEqual(result['equipment'][1]['documents'],['STD-1']);self.assertIn('Crane',op['equipment'])
    def test_equipment_document_is_not_operation_document(self):
        t=empty_tables();t['processes'].append(dict(id='TP1'))
        add_operation(t,'TP1',1,1,{},[dict(cell=cell('Tool'))],[
            dict(cell=cell('OP-DOC'),scope='operation',resource_indices=[1]),
            dict(cell=cell('TOOL-STD'),scope='equipment',resource_indices=[1])])
        result=public_tables(t)
        self.assertEqual(result['operations'][0]['document'],'OP-DOC')
        self.assertEqual(result['equipment'][0]['documents'],['OP-DOC','TOOL-STD'])
