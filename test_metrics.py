import unittest
from tpocr import distance, normalize

class MetricsTests(unittest.TestCase):
    def test_insertions(self):
        self.assertEqual(distance('аб','абвгд'),3)
    def test_substitution_deletion(self):
        self.assertEqual(distance('станок','станки'),2)
    def test_word_order(self):
        self.assertEqual(distance(['режим','резания'],['резания','режим']),2)
    def test_normalize(self):
        self.assertEqual(normalize('  Ёж\n  А ',True),'еж а')
    def test_empty_prediction(self):
        self.assertEqual(distance('текст',''),5)

if __name__=='__main__': unittest.main()
