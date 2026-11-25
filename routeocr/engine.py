from pathlib import Path
import csv, io, subprocess

class EasyEngine:
    def __init__(self, models, gpu=False):
        import os
        os.environ['EASYOCR_MODULE_PATH']=str(Path(models).resolve())
        import easyocr
        import torch
        if gpu:
            if not torch.cuda.is_available():raise ValueError('CUDA unavailable. Use CPU bundle or install compatible CUDA wheels.')
            capability=torch.cuda.get_device_capability()
            arch=f'sm_{capability[0]}{capability[1]}'
            arches=torch.cuda.get_arch_list()
            # Pascal sm_61 may execute sm_60 cubins of the same major generation.
            compatible=any(a.startswith(f'sm_{capability[0]}') and int(a.split('_')[1])<=capability[0]*10+capability[1] for a in arches)
            if not compatible:raise ValueError(f'GPU {arch} unsupported by this PyTorch build: {arches}')
        self.reader=easyocr.Reader(['ru','en'],gpu=gpu,model_storage_directory=str(Path(models).resolve()),
                                   user_network_directory=str(Path(models).resolve()/'user_network'),download_enabled=False,verbose=False)
    def read(self,image,numeric=False,fieldname=None):
        alphabet=None
        if fieldname=='content' or (fieldname or '').startswith('resource_'):
            alphabet='АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789.,-/=():; Q'
        if numeric:
            entries=self.reader.readtext(image,detail=1,paragraph=False,decoder='beamsearch',beamWidth=5,
                batch_size=1,workers=0,min_size=3,allowlist='0123456789.,/-')
            if not entries:
                import cv2, numpy as np
                gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
                # Dark-ink crop excludes pale ruling; preserve original crop for review.
                blur=cv2.GaussianBlur(gray,(0,0),15)
                normalized=cv2.divide(gray,blur,scale=255)
                mask=cv2.threshold(normalized,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
                count,labels,stats,centroids=cv2.connectedComponentsWithStats(mask)
                h,w=gray.shape
                components=[r for r in stats[1:] if r[4]>=max(8,h*w*.004) and r[2]<w*.95 and r[3]<h*.95]
                if components:
                    x=min(r[0] for r in components);y=min(r[1] for r in components)
                    x2=max(r[0]+r[2] for r in components);y2=max(r[1]+r[3] for r in components)
                    tight=gray[y:y2,x:x2]
                    if len(components)==1 and tight.shape[1]>3*tight.shape[0] and tight.shape[0]<h*.25:
                        entries=[([[x,y],[x2,y],[x2,y2],[x,y2]],'-',.5)]
                    else:
                        padded=cv2.copyMakeBorder(tight,8,8,8,8,cv2.BORDER_CONSTANT,value=255)
                        ph,pw=padded.shape
                        recognized=self.reader.recognize(padded,horizontal_list=[[0,pw,0,ph]],free_list=[],detail=1,
                            decoder='beamsearch',beamWidth=5,batch_size=1,workers=0,allowlist='0123456789.,/-')
                        entries=[([[x,y],[x2,y],[x2,y2],[x,y2]],t,min(float(c),.5)) for _,t,c in recognized]
        else:
            entries=self.reader.readtext(image,detail=1,paragraph=False,decoder='beamsearch',beamWidth=5,
                                         batch_size=1,workers=0,min_size=3,allowlist=alphabet)
        words=[]
        for polygon,text,confidence in entries:
            if not text.strip():continue
            xs=[float(p[0]) for p in polygon];ys=[float(p[1]) for p in polygon]
            words.append(dict(text=text,confidence=float(confidence),bbox=[min(xs),min(ys),max(xs),max(ys)]))
        # Group by baseline; multiline cells retain explicit newlines.
        lines=[]
        for word in sorted(words,key=lambda w:(w['bbox'][1]+w['bbox'][3])/2):
            y=(word['bbox'][1]+word['bbox'][3])/2;h=word['bbox'][3]-word['bbox'][1]
            if lines and abs(y-lines[-1]['y'])<max(4,h*.55):lines[-1]['words'].append(word)
            else:lines.append(dict(y=y,words=[word]))
        text='\n'.join(' '.join(w['text'] for w in sorted(line['words'],key=lambda w:w['bbox'][0])) for line in lines)
        return dict(decoding_constraints='numeric alphabet; undetected symbols use ink crop fallback (confidence <= 0.5)' if numeric else ('Cyrillic text alphabet' if alphabet else 'none'),text=text,confidence=sum(w['confidence']*len(w['text']) for w in words)/sum(len(w['text']) for w in words) if words else 0,words=words)

class TesseractEngine:
    def __init__(self,models,executable='tesseract'):
        self.models=models;self.executable=executable
    def read(self,image,numeric=False,fieldname=None):
        import cv2
        ok,data=cv2.imencode('.png',image)
        if not ok:raise ValueError('Cannot encode crop')
        cmd=[self.executable,'stdin','stdout','--tessdata-dir',self.models,'-l','rus+eng','--psm','6',
             '-c','tessedit_create_tsv=1','-c','tessedit_create_txt=0']
        r=subprocess.run(cmd,input=data.tobytes(),capture_output=True,timeout=120)
        if r.returncode:raise ValueError(r.stderr.decode(errors='replace'))
        words=[];lines={}
        for row in csv.DictReader(io.StringIO(r.stdout.decode('utf-8')),delimiter='\t',quoting=csv.QUOTE_NONE):
            if row['level']!='5' or not row['text'].strip():continue
            x,y,w,h=[int(row[k]) for k in ['left','top','width','height']]
            word=dict(text=row['text'],confidence=float(row['conf'])/100,bbox=[x,y,x+w,y+h]);words.append(word)
            key=tuple(row[k] for k in ['block_num','par_num','line_num']);lines.setdefault(key,[]).append(row['text'])
        return dict(text='\n'.join(' '.join(x) for x in lines.values()),confidence=sum(w['confidence'] for w in words)/len(words) if words else 0,words=words)
