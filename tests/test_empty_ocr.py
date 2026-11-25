import unittest
import numpy as np
from routeocr.engine import EasyEngine
class EmptyOCR(unittest.TestCase):
    def test_empty_detection_text_does_not_divide_by_zero(self):
        class Reader:
            def readtext(self,*args,**kwargs):return [([[0,0],[10,0],[10,10],[0,10]],'',0)]
        engine=EasyEngine.__new__(EasyEngine);engine.reader=Reader()
        result=engine.read(np.full((20,20,3),255,np.uint8),numeric=True)
        self.assertEqual(result['text'],'');self.assertEqual(result['confidence'],0)
