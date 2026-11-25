import unittest
import numpy as np,cv2
from routeocr.digits import prepare_single_digit,classify_digit,SHAPES
class Digits(unittest.TestCase):
    def test_blank_and_two_digits_rejected(self):
        im=np.full((70,90),255,np.uint8)
        with self.assertRaises(ValueError):prepare_single_digit(im)
        cv2.rectangle(im,(10,10),(20,60),0,-1);cv2.rectangle(im,(50,10),(60,60),0,-1)
        with self.assertRaises(ValueError):prepare_single_digit(im)
    def test_aspect_ratio_and_numpy_dense_inference(self):
        im=np.full((70,50),255,np.uint8);cv2.rectangle(im,(22,10),(26,60),0,-1)
        x=prepare_single_digit(im);self.assertEqual(x.shape,(1,784));self.assertLess(np.count_nonzero(x),150)
        weights={k:np.zeros(v,np.float32) for k,v in SHAPES.items()};weights['b3'][7]=8
        candidate=classify_digit(im,weights);self.assertEqual(candidate['candidate'],'7');self.assertTrue(candidate['needs_review'])
