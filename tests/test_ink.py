import unittest
import cv2,numpy as np
from routeocr.image import suppress_bleed
class InkFilter(unittest.TestCase):
    def test_faint_marks_suppressed_dark_strokes_retained(self):
        im=np.full((100,200,3),235,np.uint8)
        cv2.line(im,(20,20),(60,20),(225,225,225),3)
        cv2.line(im,(20,60),(60,60),(100,100,100),3)
        out,stats=suppress_bleed(im,min_contrast=18)
        self.assertTrue(np.all(out[20,40]==255));self.assertTrue(np.all(out[60,40]==100))
    def test_strict_threshold_can_delete_real_light_ink(self):
        im=np.full((60,100,3),235,np.uint8);cv2.line(im,(20,30),(70,30),(220,220,220),3)
        out,_=suppress_bleed(im,min_contrast=18);self.assertTrue(np.all(out[30,40]==255))
    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):suppress_bleed(np.zeros((20,20,3),np.uint8),min_contrast=300)
