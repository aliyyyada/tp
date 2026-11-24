"""Lossless entities and relations. No silent correction of engineering values."""
from dataclasses import dataclass, field, asdict
import re

FIELDS = ['shop','section','number','operation_code','content','worker_grade','worker_code',
          'normalization_unit','simultaneous_parts','batch_size','piece_time','equipment_number']
NUMERIC = {'shop','section','number','worker_grade','worker_code','normalization_unit',
           'simultaneous_parts','batch_size','piece_time','equipment_number'}
TABLES = ['processes','operations','resources','documents','operation_resources',
          'operation_documents','resource_documents','review']


def empty_tables():
    return {k: [] for k in TABLES}


def add_operation(tables, process_id, page, index, cells, resources, documents, threshold=.65, continuation_of=None):
    oid = f'{process_id}/p{page}/o{index}'
    values = {k: cells.get(k, {}).get('text', '') for k in FIELDS}
    if continuation_of:
        oid=f'{process_id}/{continuation_of}'
        matches=[o for o in tables['operations'] if o['id']==oid]
        if not matches:raise ValueError('Unknown continuation target: '+oid)
        op=matches[0];op.setdefault('continuation_pages',[]).append(page)
        for key,value in values.items():
            if value.strip():
                if op.get(key) and op[key]!=value:
                    op.setdefault('continuation_values',[]).append(dict(page=page,field=key,value=value))
                    tables['review'].append(dict(operation_id=oid,field=key,reason='continuation_conflict'))
                else:op[key]=value
        op.setdefault('continuation_cells',[]).append(dict(page=page,cells=cells))
    else:
        tables['operations'].append(dict(id=oid,process_id=process_id,page=page,**values,
                                         raw_cells=cells,needs_review=True))
    for name,c in cells.items():
        if not c['text'].strip() or c.get('confidence',0) < threshold:
            tables['review'].append(dict(operation_id=oid,field=name,reason='empty_or_low_confidence'))
        if name in NUMERIC and c['text'].strip() and not re.fullmatch(r'[\d\s.,/\-]+',c['text']):
            tables['review'].append(dict(operation_id=oid,field=name,reason='unexpected_numeric_characters'))
    rids=[]
    for i,item in enumerate(resources):
        rid=f'{oid}/p{page}b{index}r{i+1}';rids.append(rid)
        tables['resources'].append(dict(id=rid,kind=item.get('kind','unknown'),
            name=item['cell']['text'],inventory_number=item.get('inventory_number',''),raw=item['cell'],inventory_evidence=item.get('inventory_evidence')))
        tables['operation_resources'].append(dict(operation_id=oid,resource_id=rid))
    for i,item in enumerate(documents):
        did=f'{oid}/p{page}b{index}d{i+1}'
        tables['documents'].append(dict(id=did,designation=item['cell']['text'],raw=item['cell'],inventory_evidence=item.get('inventory_evidence')))
        tables['operation_documents'].append(dict(operation_id=oid,document_id=did))
        # Only explicit template links. Never pair resources/documents by OCR order.
        for resource_index in item.get('resource_indices',[]):
            if not 1 <= resource_index <= len(rids):
                raise ValueError('Document resource_indices outside resource list')
            tables['resource_documents'].append(dict(resource_id=rids[resource_index-1],document_id=did))
        if rids and not item.get('resource_indices'):
            tables['review'].append(dict(operation_id=oid,field='resource_documents',reason='association_not_verified',document_id=did))
    return oid


def validate_relations(t):
    ids={name:{r['id'] for r in t[name]} for name in ['processes','operations','resources','documents']}
    for name in ids:
        if len(ids[name])!=len(t[name]):raise ValueError('Duplicate IDs: '+name)
    for op in t['operations']:
        if op['process_id'] not in ids['processes']:raise ValueError('Unknown process')
    links={'operation_resources': [('operation_id','operations'),('resource_id','resources')],
           'operation_documents':[('operation_id','operations'),('document_id','documents')],
           'resource_documents':[('resource_id','resources'),('document_id','documents')]}
    for table,columns in links.items():
        for row in t[table]:
            for key,target in columns:
                if row[key] not in ids[target]:raise ValueError(f'Broken link {table}.{key}')
    for row in t['resource_documents']:
        rops={x['operation_id'] for x in t['operation_resources'] if x['resource_id']==row['resource_id']}
        dops={x['operation_id'] for x in t['operation_documents'] if x['document_id']==row['document_id']}
        if not rops.intersection(dops):raise ValueError('Cross-operation document/resource link')
