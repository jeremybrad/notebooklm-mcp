"""Individual original Markdown lifecycle in the existing notebook map.

Selection is owned by source_bundle. No creation, enrollment, credentials or
scheduler. Injected transport writes must enforce the exact strong ETag; live
conditional-write qualification remains a separate release requirement.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import re
import uuid

from .drive_publication import SourceText
from .publication_state import MapStore, StateError, _hash, _keys, _label
from .selection import normalize_relpath

KEY = 'drive_documents'
MAX_CONTENT_BYTES = 4 * 1024 * 1024


def _path(value):
    _label(value)
    if normalize_relpath(value) != value or '\\' in value or not value.lower().endswith('.md'):
        raise StateError('Expected canonical relative Markdown path')


def _etag(value):
    if not isinstance(value, str) or not re.fullmatch(r'"[\x21\x23-\x7e]{1,1024}"', value):
        raise StateError('Strong file ETag required')


def digest(content):
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    file_id: str
    etag: str
    content: bytes

    def __post_init__(self):
        _label(self.file_id); _etag(self.etag)
        if not isinstance(self.content, bytes) or len(self.content) > MAX_CONTENT_BYTES:
            raise StateError('Invalid Markdown snapshot')


def document_key(source):
    """Provider key includes repository and full path; repeated names cannot collide."""
    _label(source.repo); _path(source.path)
    return digest((source.repo + '\0' + source.path).encode('utf-8'))


def _provenance(value):
    _keys(value, {'commit', 'blob_oid', 'manifest_hash_prefix'})
    for key in ('commit', 'blob_oid'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value[key]):
            raise StateError('Immutable Git provenance required')
    if not isinstance(value['manifest_hash_prefix'], str) or not re.fullmatch(r'[0-9a-f]{12}', value['manifest_hash_prefix']):
        raise StateError('Inspected manifest provenance required')


def validate_documents(record, destinations):
    """Share whole-map collision checking with the existing native Docs bindings."""
    _label(record.get('notebook_id'))
    documents = record[KEY]
    if not isinstance(documents, dict): raise StateError('Document bindings must be a mapping')
    for path, entry in documents.items():
        _path(path)
        _keys(entry, {'version', 'file_id', 'verified', 'pending', 'notebook'})
        if type(entry['version']) is not int or entry['version'] != 1: raise StateError('Unsupported document version')
        _label(entry['file_id'])
        if entry['file_id'] in destinations: raise StateError('Cloud file has multiple bindings')
        destinations.add(entry['file_id'])
        verified = entry['verified']; _keys(verified, {'sha256', 'etag', 'source'})
        _hash(verified['sha256']); _etag(verified['etag'])
        if verified['source'] is not None: _provenance(verified['source'])
        pending = entry['pending']
        if pending is not None:
            _keys(pending, {'operation_id', 'base_sha256', 'base_etag', 'target_sha256', 'source'})
            if not isinstance(pending['operation_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', pending['operation_id']): raise StateError('Invalid operation identity')
            _hash(pending['target_sha256']); _etag(pending['base_etag']); _provenance(pending['source'])
            if pending['base_sha256'] != verified['sha256']: raise StateError('Pending base mismatch')
        if entry['notebook'] is not None:
            _keys(entry['notebook'], {'sha256', 'source_id', 'evidence'})
            _hash(entry['notebook']['sha256']); _label(entry['notebook']['source_id']); _label(entry['notebook']['evidence'])


def _target(source, receipt):
    document_key(source)
    raw = source.text.encode('utf-8')
    if not raw.strip() or len(raw) > MAX_CONTENT_BYTES: raise StateError('Empty/oversize original')
    matches = [r for r in receipt['sources'] if r['path'] == source.path]
    if (receipt.get('repo') != source.repo or len(matches) != 1
            or matches[0]['blob_oid'] != source.source_revision
            or matches[0]['sha256'] != digest(raw) or matches[0]['byte_count'] != len(raw)):
        raise StateError('Source bytes/provenance mismatch')
    provenance = {k: receipt[k] for k in ('commit', 'manifest_hash_prefix')}
    provenance['blob_oid'] = source.source_revision
    _provenance(provenance)
    return raw, provenance


def _entry(data, source):
    try: return data['notebooks'][source.repo][KEY][source.path]
    except KeyError: raise StateError('Original has no explicit file binding') from None


def _read(transport, file_id):
    snapshot = transport.read(file_id)
    if not isinstance(snapshot, Snapshot) or snapshot.file_id != file_id: raise StateError('Remote identity mismatch')
    return snapshot


def bind_empty(store, source, notebook_id, snapshot):
    """Explicit adoption of a caller-inspected empty file. Creates no cloud object."""
    document_key(source); _label(notebook_id)
    if not isinstance(snapshot, Snapshot) or snapshot.content != b'': raise StateError('Only empty files may be adopted')
    with store.transaction() as transaction:
        old = store.read(); data = deepcopy(old.data)
        record = data['notebooks'].setdefault(source.repo, {'notebook_id': notebook_id})
        if record.get('notebook_id') != notebook_id: raise StateError('Notebook identity mismatch')
        documents = record.setdefault(KEY, {})
        if source.path in documents: raise StateError('Original already bound')
        documents[source.path] = {'version': 1, 'file_id': snapshot.file_id,
            'verified': {'sha256': digest(b''), 'etag': snapshot.etag, 'source': None},
            'pending': None, 'notebook': None}
        transaction.save(old, data)


def publish(store, source, receipt, transport):
    raw, provenance = _target(source, receipt)
    with store.transaction() as transaction:
        old = store.read(); data = deepcopy(old.data); entry = _entry(data, source)
        if entry['pending'] is not None: raise StateError('Reconcile pending intent first')
        remote = _read(transport, entry['file_id'])
        if digest(remote.content) != entry['verified']['sha256']: raise StateError('Remote manual edit')
        if remote.content == raw: return 'unchanged'
        entry['pending'] = {'operation_id': uuid.uuid4().hex,
            'base_sha256': entry['verified']['sha256'], 'base_etag': remote.etag,
            'target_sha256': digest(raw), 'source': provenance}
        old = transaction.save(old, data)
        transport.write(remote.file_id, raw, remote.etag)
        after = _read(transport, remote.file_id)
        if after.content != raw: raise StateError('Readback mismatch; pending retained')
        entry['verified'] = {'sha256': digest(raw), 'etag': after.etag, 'source': provenance}
        entry['pending'] = None
        transaction.save(old, data)
        return 'replace_bytes'


def reconcile(store, source, receipt, transport):
    """Read-only remote reconciliation; never replay or silently adopt another input."""
    raw, provenance = _target(source, receipt)
    with store.transaction() as transaction:
        old = store.read(); data = deepcopy(old.data); entry = _entry(data, source)
        pending = entry['pending']
        if pending is None or pending['target_sha256'] != digest(raw) or pending['source'] != provenance:
            raise StateError('Original pending input required')
        remote = _read(transport, entry['file_id'])
        if remote.content == raw:
            entry['verified'] = {'sha256': digest(raw), 'etag': remote.etag, 'source': provenance}
            action = 'verified_target'
        elif digest(remote.content) == pending['base_sha256']:
            action = 'verified_base'
        else: raise StateError('Remote matches neither pending base nor target')
        entry['pending'] = None
        transaction.save(old, data)
        return action


def verify_sibling(store, source, receipt, transport):
    """Read back an exact already-verified recovery sibling without changing state."""
    raw, provenance = _target(source, receipt)
    with store.transaction():
        entry = _entry(store.read().data, source)
        if (entry['pending'] is not None or entry['verified']['sha256'] != digest(raw)
                or entry['verified']['source'] != provenance):
            raise StateError('Exact verified sibling required')
        remote = _read(transport, entry['file_id'])
        if remote.content != raw:
            raise StateError('Remote verified sibling changed')
        return 'verified_sibling'
