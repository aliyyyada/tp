import argparse, csv, json, re
from pathlib import Path
from .model import FIELDS, NUMERIC, empty_tables, add_operation, validate_relations

def dump(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def render(pdf,number,dpi):
    import fitz, numpy as np, cv2
    with fitz.open(pdf) as doc:
        if number<1 or number>len(doc):raise ValueError('Page outside PDF')
        p=doc[number-1].get_pixmap(dpi=dpi,colorspace=fitz.csRGB,alpha=False)
        return cv2.cvtColor(np.frombuffer(p.samples,np.uint8).reshape(p.height,p.width,3),cv2.COLOR_RGB2BGR)

def preview(args):
    import cv2
    from .image import rectify,box_pixels
    t=load(args.template);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    for page in t['pages']:
        im=rectify(render(args.pdf,page['page'],args.dpi),page)
        overlay=im.copy()
        for index,row in enumerate(page['rows'],1):
            boxes=dict(row['cells'])
            if page.get('process_number_box'):boxes['process_document_number']=page['process_number_box']
            boxes.update({f'resource_{i}':r['box'] for i,r in enumerate(row.get('resources',[]),1)})
            boxes.update({f'inventory_{i}':r['inventory_box'] for i,r in enumerate(row.get('resources',[]),1) if 'inventory_box' in r})
            boxes.update({f'document_{i}':r['box'] for i,r in enumerate(row.get('documents',[]),1)})
            for name,box in boxes.items():
                x1,y1,x2,y2=box_pixels(box,im.shape);cv2.rectangle(overlay,(x1,y1),(x2,y2),(0,0,255),2)
                cv2.putText(overlay,f'{index}:{name}',(x1,y1+15),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,200),1)
        cv2.imwrite(str(out/f'page_{page["page"]:03d}_rectified.png'),im)
        cv2.imwrite(str(out/f'page_{page["page"]:03d}_boxes.png'),overlay)
    print('Inspect overlays before OCR:',out)

def export(tables,out):
    import openpyxl
    validate_relations(tables);dump(out/'result.json',tables)
    wb=openpyxl.Workbook();wb.remove(wb.active)
    for name,rows in tables.items():
        # Preserve schema even on an empty relation sheet.
        columns=list(dict.fromkeys(k for row in rows for k in row)) or ['id']
        def value(x):return json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list)) else x
        with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow(columns)
            for row in rows:writer.writerow([value(row.get(k,'')) for k in columns])
        ws=wb.create_sheet(name);ws.append(columns)
        for row in rows:
            for j,k in enumerate(columns,1):
                v=value(row.get(k,''));cell=ws.cell(ws.max_row+1,j,v) if j==1 else ws.cell(ws.max_row,j,v)
                # Spreadsheet text is never interpreted as a formula.
                if isinstance(v,str):cell.data_type='s'
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    wb.save(out/'tables.xlsx')

def ocr(args):
    import cv2
    from .image import rectify,crop_variant
    from .engine import EasyEngine,TesseractEngine
    template=load(args.template)
    if template.get('requires_calibration') and not args.accept_template:raise ValueError('Template is illustrative. Calibrate and set requires_calibration=false, or explicitly --accept-template for a trial.')
    out=Path(args.output)
    if out.exists() and any(out.iterdir()):raise ValueError('Output must be a new/empty directory')
    out.mkdir(parents=True,exist_ok=True);(out/'crops').mkdir()
    engine=EasyEngine(args.models,args.gpu) if args.engine=='easyocr' else TesseractEngine(args.models,args.tesseract)
    tables=empty_tables();pid=args.process_id
    tables['processes'].append(dict(id=pid,document_number=args.document_number or '',source=Path(args.pdf).name,number_source='user_supplied' if args.document_number else 'not_set',needs_review=True))
    evidence=[]
    for page in template['pages']:
        n=page['page'];im=rectify(render(args.pdf,n,args.dpi),page)
        cv2.imwrite(str(out/f'page_{n:03d}_rectified.png'),im)
        if page.get('process_number_box') and not args.document_number:
            crop,bbox=crop_variant(im,page['process_number_box'],args.variant)
            cv2.imwrite(str(out/'crops'/'process_document_number.png'),crop)
            header=engine.read(crop,False,fieldname='document_number')
            header.update(key='process/document_number',crop='crops/process_document_number.png',bbox=bbox,reviewed=False)
            evidence.append(header)
            tables['processes'][0].update(document_number=header['text'],number_source='header_ocr_candidate',raw_number=header)
        for index,row in enumerate(page['rows'],1):
            def read(name,box):
                crop,bbox=crop_variant(im,box,args.variant)
                fname=f'p{n:03d}_o{index:03d}_{name}.png';cv2.imwrite(str(out/'crops'/fname),crop)
                cell=engine.read(crop,name in NUMERIC,fieldname=name)
                cell.update(crop='crops/'+fname,bbox=bbox,variant=args.variant,word_coordinate_system='crop pixels incl 12px padding',reviewed=False)
                evidence.append(dict(key=f'p{n}/o{index}/{name}',**cell))
                return cell
            cells={name:read(name,box) for name,box in row['cells'].items()}
            resources=[]
            for i,r in enumerate(row.get('resources',[]),1):
                resource=dict(r,cell=read(f'resource_{i}',r['box']))
                if 'inventory_box' in r:
                    inventory=read(f'inventory_{i}',r['inventory_box'])
                    resource['inventory_number']=inventory['text'];resource['inventory_evidence']=inventory
                resources.append(resource)
            docs=[dict(d,cell=read(f'document_{i}',d['box'])) for i,d in enumerate(row.get('documents',[]),1)]
            add_operation(tables,pid,n,index,cells,resources,docs,args.threshold,row.get('continuation_of'))
            print(f'Page {n}, operation band {index}',flush=True)
    export(tables,out);dump(out/'cells.json',evidence)
    dump(out/'run.json',dict(engine=args.engine,variant=args.variant,dpi=args.dpi,gpu=args.gpu,template=template,
                             note='Every operation requires review; OCR confidence is not accuracy.'))
    dump(out/'reference.template.json',[dict(key=c['key'],text='',verified=False) for c in evidence])

def evaluate(args):
    from tpocr import distance,normalize
    pred=load(args.prediction);refs=load(args.reference)
    p={c['key']:c['text'] for c in pred}
    if len(p)!=len(pred):raise ValueError('Duplicate prediction keys')
    if not refs or len({r['key'] for r in refs})!=len(refs):raise ValueError('Empty reference or duplicate reference keys')
    rows=[]
    for r in refs:
        if r.get('verified') is not True:raise ValueError('Every reference cell must be manually verified')
        if r['key'] not in p:raise ValueError('Missing cell: '+r['key'])
        a,b=normalize(r['text'],args.relaxed),normalize(p[r['key']],args.relaxed)
        rows.append(dict(key=r['key'],char_errors=distance(a,b),chars=len(a),word_errors=distance(a.split(),b.split()),words=len(a.split()),exact=a==b))
    chars=sum(r['chars'] for r in rows);words=sum(r['words'] for r in rows)
    ce=sum(r['char_errors'] for r in rows);we=sum(r['word_errors'] for r in rows)
    report=dict(cer=ce/chars if chars else None,wer=we/words if words else None,exact_cell_accuracy=sum(r['exact'] for r in rows)/len(rows),
                char_errors=ce,reference_chars=chars,word_errors=we,reference_words=words,evaluated_cells=len(rows),predicted_cells=len(pred),
                reference_coverage=len(rows)/len(pred) if pred else 0,relaxed=args.relaxed,cells=rows)
    dump(args.output,report);print(json.dumps({k:v for k,v in report.items() if k!='cells'},ensure_ascii=False,indent=2))

def main():
    p=argparse.ArgumentParser(description='Offline route-card cells OCR and relational export')
    sub=p.add_subparsers(dest='command',required=True)
    for name,func in [('preview',preview),('ocr',ocr)]:
        a=sub.add_parser(name);a.add_argument('pdf');a.add_argument('--template',required=True);a.add_argument('-o','--output',required=True);a.add_argument('--dpi',type=int,choices=range(100,601),default=240);a.set_defaults(func=func)
        if name=='ocr':
            a.add_argument('--process-id',required=True);a.add_argument('--document-number',help='Verified document number; otherwise template header OCR candidate');a.add_argument('--models',default='models');a.add_argument('--engine',choices=['easyocr','tesseract'],default='easyocr')
            a.add_argument('--tesseract',default='tesseract');a.add_argument('--gpu',action='store_true');a.add_argument('--accept-template',action='store_true')
            a.add_argument('--variant',choices=['original','gray','clahe','binary'],default='original');a.add_argument('--threshold',type=float,default=.65)
    a=sub.add_parser('evaluate');a.add_argument('prediction');a.add_argument('reference');a.add_argument('-o','--output',default='metrics.json');a.add_argument('--relaxed',action='store_true');a.set_defaults(func=evaluate)
    args=p.parse_args()
    try:args.func(args)
    except (ValueError,OSError,KeyError) as e:p.exit(1,f'Error: {e}\n')
if __name__=='__main__':main()
