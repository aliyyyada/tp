import cv2
import numpy as np

def box_pixels(box,shape):
    if len(box)!=4 or not all(isinstance(v,(int,float)) for v in box):raise ValueError('Box must contain 4 numbers')
    x1,y1,x2,y2=box
    if not 0<=x1<x2<=1 or not 0<=y1<y2<=1:raise ValueError(f'Invalid normalized box: {box}')
    h,w=shape[:2];return int(x1*w),int(y1*h),max(int(x2*w),int(x1*w)+1),max(int(y2*h),int(y1*h)+1)

def rectify(image,page):
    rotation=page.get('rotation',0)
    if rotation not in (0,90,180,270):raise ValueError('rotation must be 0/90/180/270 clockwise')
    image=np.rot90(image,-rotation//90).copy()
    if 'corners' not in page:return image
    corners=np.asarray(page['corners'],dtype=np.float32)
    if corners.shape!=(4,2) or np.any(corners<0) or np.any(corners>1):raise ValueError('corners: four normalized points TL,TR,BR,BL after rotation')
    h,w=image.shape[:2];corners*=np.array([w,h],np.float32)
    if not cv2.isContourConvex(corners.astype(np.int32)):raise ValueError('Corners must form a convex quadrilateral')
    width=int(max(np.linalg.norm(corners[1]-corners[0]),np.linalg.norm(corners[2]-corners[3])))
    height=int(max(np.linalg.norm(corners[3]-corners[0]),np.linalg.norm(corners[2]-corners[1])))
    if min(width,height)<32:raise ValueError('Rectified image too small')
    target=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    return cv2.warpPerspective(image,cv2.getPerspectiveTransform(corners,target),(width,height),borderValue=(255,255,255))

def crop_variant(image,box,variant):
    x1,y1,x2,y2=box_pixels(box,image.shape)
    crop=image[y1:y2,x1:x2].copy()
    if variant=='gray':crop=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    elif variant=='clahe':
        lab=cv2.cvtColor(crop,cv2.COLOR_BGR2LAB);lab[:,:,0]=cv2.createCLAHE(2,(8,8)).apply(lab[:,:,0]);crop=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
    elif variant=='binary':
        gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
        bg=cv2.GaussianBlur(gray,(0,0),21);gray=cv2.divide(gray,bg,scale=255)
        crop=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    elif variant!='original':raise ValueError('Unknown preprocessing variant')
    # No unconditional thresholding: preserve weak handwriting in original/CLAHE modes.
    crop=cv2.copyMakeBorder(crop,12,12,12,12,cv2.BORDER_CONSTANT,value=255 if crop.ndim==2 else (255,255,255))
    return crop,[x1,y1,x2,y2]
