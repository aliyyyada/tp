"""Optional single-digit Dense MNIST inference, NumPy only. No pretrained weights included."""
from pathlib import Path
import numpy as np
import cv2

SHAPES={'w1':(784,784),'b1':(784,), 'w2':(784,200),'b2':(200,), 'w3':(200,10),'b3':(10,)}

def load_weights(path):
    with np.load(path,allow_pickle=False) as archive:
        weights={k:np.asarray(archive[k],dtype=np.float32) for k in SHAPES}
    for k,shape in SHAPES.items():
        if weights[k].shape!=shape or not np.isfinite(weights[k]).all():raise ValueError('Invalid MNIST weights: '+k)
    return weights


def prepare_single_digit(image):
    if image is None:raise ValueError('Cannot open image')
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
    # MNIST polarity: bright ink on black background, aspect ratio retained.
    ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    n,labels,stats,_=cv2.connectedComponentsWithStats(ink)
    components=[(i,s) for i,s in enumerate(stats[1:],1) if s[4]>=max(3,ink.size*.001)]
    if len(components)!=1:raise ValueError('Expected ONE isolated connected digit; blank, punctuation, touching digits and grid lines require manual segmentation')
    index,(x,y,w,h,area)=components[0]
    if w/max(h,1)>1.5:raise ValueError('Wide mark: may be punctuation or multiple touching digits')
    glyph=ink[y:y+h,x:x+w]
    scale=20/max(w,h);resized=cv2.resize(glyph,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
    canvas=np.zeros((28,28),np.float32);hh,ww=resized.shape
    canvas[(28-hh)//2:(28-hh)//2+hh,(28-ww)//2:(28-ww)//2+ww]=resized/255
    moments=cv2.moments(canvas)
    if moments['m00']:
        dx=13.5-moments['m10']/moments['m00'];dy=13.5-moments['m01']/moments['m00']
        canvas=cv2.warpAffine(canvas,np.float32([[1,0,dx],[0,1,dy]]),(28,28))
    return canvas.reshape(1,784)


def classify_digit(image,weights):
    x=prepare_single_digit(image)
    for index in (1,2):x=np.maximum(0,x@weights[f'w{index}']+weights[f'b{index}'])
    logits=x@weights['w3']+weights['b3'];exp=np.exp(logits-logits.max(axis=1,keepdims=True));probabilities=exp/exp.sum(axis=1,keepdims=True)
    return dict(candidate=str(int(np.argmax(probabilities))),confidence=float(probabilities.max()),
                probabilities=probabilities[0].tolist(),needs_review=True,
                note='Single-digit candidate only. Confidence is not measured accuracy; segmentation is not guaranteed.')
