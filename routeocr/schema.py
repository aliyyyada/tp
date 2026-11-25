"""Public data contract: exactly three entities, independent of OCR audit tables."""
from .model import validate_relations

COLUMNS = {
    'documents':['id','document_number','source','number_source','needs_review'],
    'operations':['id','document_id','page','continuation_pages','shop','section','number','operation_code',
        'content','document','equipment_ids','equipment','worker_grade','worker_code',
        'normalization_unit','simultaneous_parts','batch_size','piece_time','needs_review'],
    'equipment':['id','document_id','operation_id','kind','name','inventory_number','documents','needs_review'],
}

def public_tables(audit):
    validate_relations(audit)
    result={k:[] for k in COLUMNS}
    for process in audit['processes']:
        result['documents'].append({k:process.get(k,'') for k in COLUMNS['documents']})
    designations={d['id']:d['designation'] for d in audit['documents']}
    resources={r['id']:r for r in audit['resources']}
    scopes={d['id']:d.get('scope','operation') for d in audit['documents']}
    for op in audit['operations']:
        oid=op['id']
        rids=[x['resource_id'] for x in audit['operation_resources'] if x['operation_id']==oid]
        docs=[designations[x['document_id']] for x in audit['operation_documents'] if x['operation_id']==oid and scopes[x['document_id']]=='operation']
        row={k:op.get(k,'') for k in COLUMNS['operations']}
        row.update(document_id=op['process_id'],document='\n'.join(docs),equipment_ids=rids,
                   equipment='\n'.join(resources[r]['name'] for r in rids))
        result['operations'].append(row)
        for rid in rids:
            r=resources[rid]
            linked=[designations[x['document_id']] for x in audit['resource_documents'] if x['resource_id']==rid]
            result['equipment'].append(dict(id=rid,document_id=op['process_id'],operation_id=oid,
                kind=r['kind'],name=r['name'],inventory_number=r.get('inventory_number',''),documents=linked,
                needs_review=True))
    return result


def apply_document_scopes(audit,template):
    """Use explicit template metadata to migrate legacy audit files without re-OCR."""
    scopes={}
    for page in template['pages']:
        for index,row in enumerate(page['rows'],1):
            for i,item in enumerate(row.get('documents',[]),1):
                scopes[f"/p{page['page']}b{index}d{i}"]=item.get('scope','operation')
    for document in audit['documents']:
        matches=[scope for suffix,scope in scopes.items() if document['id'].endswith(suffix)]
        if len(matches)==1:document['scope']=matches[0]
    return audit
