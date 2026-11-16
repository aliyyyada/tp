"""Offline OCR of scanned technological cards. Python 3.11+."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(x != y)))
        previous = current
    return previous[-1]


def normalize(text, relaxed=False):
    text = unicodedata.normalize('NFC', text)
    if relaxed:
        text = text.casefold().replace('ё', 'е')
    return ' '.join(text.split())


def evaluate(args):
    predicted = json.loads(Path(args.prediction).read_text(encoding='utf-8'))
    reference = json.loads(Path(args.reference).read_text(encoding='utf-8'))
    refs = reference['pages']
    if not refs or any(not p.get('verified') or not p.get('text', '').strip() for p in refs):
        raise ValueError('Эталон должен содержать непустой текст и verified=true у каждой страницы')
    pred = {p['page']: p['text'] for p in predicted['pages']}
    if len(pred) != len(predicted['pages']) or len({p['page'] for p in refs}) != len(refs):
        raise ValueError('Повторяющиеся номера страниц')
    rows = []
    for p in refs:
        if p['page'] not in pred:
            raise ValueError(f"В результате отсутствует страница {p['page']}")
        a, b = normalize(p['text'], args.relaxed), normalize(pred[p['page']], args.relaxed)
        ce, we = distance(a, b), distance(a.split(), b.split())
        rows.append(dict(page=p['page'], char_errors=ce, reference_chars=len(a),
                         word_errors=we, reference_words=len(a.split()),
                         cer=ce/len(a), wer=we/len(a.split())))
    ce, nc = sum(r['char_errors'] for r in rows), sum(r['reference_chars'] for r in rows)
    we, nw = sum(r['word_errors'] for r in rows), sum(r['reference_words'] for r in rows)
    report = dict(cer=ce/nc, wer=we/nw, char_errors=ce, reference_chars=nc,
                  word_errors=we, reference_words=nw, relaxed=args.relaxed, pages=rows,
                  note='CER/WER могут быть больше 1 из-за вставок. Это ошибки, меньше — лучше.')
    write_json(args.output, report)
    print(f'CER: {ce/nc:.2%}; WER: {we/nw:.2%}')


def tess_command(args):
    candidates = [args.tesseract, os.environ.get('TESSERACT_CMD'), shutil.which('tesseract'),
                  r'C:\Program Files\Tesseract-OCR\tesseract.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ValueError('Tesseract не найден: используйте --tesseract путь/к/tesseract.exe')


def run_tess(exe, image, args, mode='tsv', psm=None):
    cmd = [exe, str(image), 'stdout', '-l', args.lang, '--psm', str(args.psm if psm is None else psm)]
    if args.tessdata:
        cmd += ['--tessdata-dir', str(Path(args.tessdata).resolve())]
    if mode == 'tsv':
        cmd += ['-c', 'tessedit_create_tsv=1', '-c', 'tessedit_create_txt=0']
    result = subprocess.run(cmd, capture_output=True, timeout=240)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout.decode('utf-8', errors='replace')


def preprocess(image, deskew=True, remove_lines=False):
    import cv2
    import numpy as np
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    background = cv2.GaussianBlur(gray, (0, 0), 21)
    gray = cv2.divide(gray, background, scale=255)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    angle = 0.0
    if deskew:
        # Hough lines give a conservative skew estimate; retain large rotations for OSD/manual.
        lines = cv2.HoughLinesP(255-binary, 1, np.pi/1800, 100,
                                minLineLength=max(80, binary.shape[1]//5), maxLineGap=20)
        angles = []
        if lines is not None:
            for x1,y1,x2,y2 in lines[:,0]:
                a = float(np.degrees(np.arctan2(y2-y1,x2-x1)))
                if abs(a) < 7:
                    angles.append(a)
        if angles:
            angle = float(np.median(angles))
            h,w = binary.shape
            matrix = cv2.getRotationMatrix2D((w/2,h/2), angle, 1)
            binary = cv2.warpAffine(binary, matrix, (w,h), borderValue=255)
    if remove_lines:
        ink = 255-binary
        h,w = ink.shape
        horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1,max(40,w//25)),np.uint8))
        vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((max(40,h//25),1),np.uint8))
        binary[cv2.bitwise_or(horizontal,vertical)>0] = 255
    return binary, angle


def recognize(args):
    import cv2
    import fitz
    import numpy as np
    exe = tess_command(args)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.input)
    selected = list(range(1,len(doc)+1)) if not args.pages else sorted(set(int(x) for x in args.pages.split(',')))
    if any(n < 1 or n > len(doc) for n in selected):
        raise ValueError('Номер страницы вне диапазона PDF')
    rotations = {}
    for item in args.rotate_page:
        n, angle = map(int,item.split(':'))
        if angle not in (0,90,180,270):
            raise ValueError('Поворот: только 0,90,180,270 по часовой стрелке')
        rotations[n] = angle
    pages = []
    for n in selected:
        pix = doc[n-1].get_pixmap(dpi=args.dpi, colorspace=fitz.csRGB, alpha=False)
        image = np.frombuffer(pix.samples, np.uint8).reshape(pix.height,pix.width,3).copy()
        rotation = rotations.get(n, 0)
        warnings = []
        if args.auto_rotate and n not in rotations:
            raw = out / f'page_{n:03d}_osd.png'
            cv2.imwrite(str(raw), cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
            try:
                osd_args = argparse.Namespace(**vars(args)); osd_args.lang = 'osd'
                osd = run_tess(exe,raw,osd_args,mode='osd',psm=0)
                match = re.search(r'Rotate: (\d+)',osd)
                confidence = re.search(r'Orientation confidence: ([\d.]+)',osd)
                if match and confidence and float(confidence[1]) >= 5:
                    rotation = int(match[1])
                else:
                    warnings.append('Низкая уверенность ориентации; проверьте поворот вручную')
            except RuntimeError as e:
                warnings.append('OSD не определил ориентацию: '+str(e)[:200])
            finally:
                raw.unlink(missing_ok=True)
        if rotation:
            image = np.rot90(image, -(rotation//90)).copy()
        binary, angle = preprocess(image, not args.no_deskew, args.remove_lines)
        path = out / f'page_{n:03d}.png'
        cv2.imwrite(str(path), binary)
        tsv = run_tess(exe,path,args)
        (out/f'page_{n:03d}.tsv').write_text(tsv,encoding='utf-8')
        words, lines = [], {}
        for row in csv.DictReader(io.StringIO(tsv),delimiter='\t', quoting=csv.QUOTE_NONE):
            if row['level'] != '5' or not row['text'].strip():
                continue
            word = dict(text=row['text'], confidence=float(row['conf']),
                        bbox=[int(row[k]) for k in ('left','top','width','height')])
            words.append(word)
            key = tuple(row[k] for k in ('block_num','par_num','line_num'))
            lines.setdefault(key, []).append(word['text'])
        text = '\n'.join(' '.join(v) for v in lines.values())
        (out/f'page_{n:03d}.txt').write_text(text,encoding='utf-8')
        page = dict(page=n,text=text,words=words,rotation_clockwise=rotation,deskew_angle=angle,
                    width=binary.shape[1],height=binary.shape[0],warnings=warnings,
                    mean_confidence=sum(w['confidence'] for w in words)/len(words) if words else None)
        pages.append(page)
        write_json(out/'result.json',dict(source=Path(args.input).name,dpi=args.dpi,language=args.lang,
                   coordinate_system='pixels of processed page PNG; bbox=x,y,width,height',pages=pages))
        print(f'Страница {n}: {len(words)} слов',flush=True)
    template = out/'reference.template.json'
    write_json(template,dict(pages=[dict(page=p['page'],verified=False,text='') for p in pages]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    ocr = sub.add_parser('ocr')
    ocr.add_argument('input'); ocr.add_argument('-o','--output', default='results')
    ocr.add_argument('--pages',help='Номера с 1 через запятую')
    ocr.add_argument('--dpi', type=int, choices=range(100,601), default=300)
    ocr.add_argument('--lang',default='rus+eng'); ocr.add_argument('--psm',type=int,choices=[3,6,11,12],default=3)
    ocr.add_argument('--tesseract'); ocr.add_argument('--tessdata')
    ocr.add_argument('--auto-rotate',action='store_true')
    ocr.add_argument('--rotate-page',action='append',default=[],help='Например 1:90; можно повторять')
    ocr.add_argument('--no-deskew',action='store_true')
    ocr.add_argument('--remove-lines',action='store_true',help='Может повредить символы: сравните CER')
    ocr.set_defaults(func=recognize)
    ev = sub.add_parser('evaluate')
    ev.add_argument('prediction'); ev.add_argument('reference'); ev.add_argument('-o','--output',default='metrics.json')
    ev.add_argument('--relaxed', action='store_true',help='Без регистра, ё=е; пробелы нормализуются всегда')
    ev.set_defaults(func=evaluate)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, RuntimeError, OSError, KeyError, subprocess.TimeoutExpired) as e:
        parser.exit(1, f'Ошибка: {e}\n')

if __name__ == '__main__':
    main()
