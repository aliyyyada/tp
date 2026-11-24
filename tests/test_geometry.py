import unittest
from routeocr.image import box_pixels,rectify
import numpy as np
class Geometry(unittest.TestCase):
    def test_box_bounds(self):
        self.assertEqual(box_pixels([.1,.2,.5,.6],(100,200,3)),(20,20,100,60))
        with self.assertRaises(ValueError):box_pixels([0,.2,1.1,.6],(100,200))
    def test_rotation(self):
        im=np.zeros((100,200,3),dtype=np.uint8);self.assertEqual(rectify(im,dict(rotation=90)).shape,(200,100,3))
