"""Pure offline preparation for the approved Drive publication pilot.

Accepts caller-supplied text, never discovers or reads source files. This is not
an export/privacy validator. Real-source integration must use the accepted manifest.
No HTTP, credentials, mapping writes, notebook operations or scheduler hooks.
"""
from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Expected text')
    # Restrict controls to LF/TAB and refuse surrogates and BMP private use.
    # U+000B is supported by Google but intentionally outside this text subset;
    # do not silently normalize it or claim Google strips it.
    if any((ord(c) < 32 and c not in '\n\t') or 0xD800 <= ord(c) <= 0xDFFF
           or 0xE000 <= ord(c) <= 0xF8FF for c in value):
        raise ValueError('Unsupported control, surrogate or private-use character')
    return value


def _label(value: str) -> str:
    value = _text(value)
    if not value.strip() or '\n' in value or '\t' in value:
        raise ValueError('Expected a nonempty single-line label')
    return value


@dataclass(frozen=True)
class SourceText:
    """Already-selected in-memory content; metadata is provenance, not authority."""
    repo: str
    path: str
    source_revision: str
    text: str


@dataclass(frozen=True)
class Bundle:
    text: str
    sha256: str
    source_count: int


def render_bundle(title: str, sources: Iterable[SourceText]) -> Bundle:
    """Render a deterministic text/Markdown publication copy with full hashes.

    No clock or repository HEAD is consulted. The caller supplies each source's
    immutable revision (not a moving branch or an unrelated current repo HEAD).
    Markdown/front matter are retained as text, not interpreted as instructions.
    """
    title = _label(title)
    selected = list(sources)
    if not selected:
        raise ValueError('A bundle needs at least one selected source')
    seen = set()
    parts = [f'# {title}\n\nDerived documentation copy. Repository sources remain authoritative.\n']
    for source in sorted(selected, key=lambda item: (item.repo, item.path)):
        repo, path = _label(source.repo), _label(source.path)
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', source.source_revision):
            raise ValueError('Source revision must be a full immutable Git object ID')
        identity = (repo, path)
        if identity in seen:
            raise ValueError('Duplicate source identity')
        seen.add(identity)
        content = _text(source.text.replace('\r\n', '\n').replace('\r', '\n'))
        content = content.rstrip('\n') + '\n'
        parts.append(
            f'\n---\n\n## {repo}/{path}\n\nSource revision: {source.source_revision}\n'
            f'Content SHA-256 (normalized text): {_digest(content)}\n\n{content}'
        )
    text = ''.join(parts)
    return Bundle(text, _digest(text), len(selected))


@dataclass(frozen=True)
class DocsSnapshot:
    document_id: str
    tab_id: str
    revision_id: str
    text: str


@dataclass(frozen=True)
class DocsBinding:
    """Expected managed destination and last verified text hash, supplied by caller."""
    document_id: str
    tab_id: str
    last_verified_sha256: str


@dataclass(frozen=True)
class UpdatePlan:
    action: str
    document_id: str
    tab_id: str
    expected_text: str
    expected_sha256: str
    body: dict[str, Any] | None


def _no_suggestions(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.startswith('suggested') and item:
                raise ValueError('Suggested changes are outside the plain-text pilot')
            _no_suggestions(item)
    elif isinstance(value, list):
        for item in value:
            _no_suggestions(item)


def _utf16_length(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def parse_document(raw: dict[str, Any]) -> DocsSnapshot:
    """Parse a complete Docs get(includeTabsContent=true) response.

    The response must explicitly report SUGGESTIONS_INLINE; callers must request
    that mode for both planning and readback. Missing/default/preview modes fail.
    Only a single tab with contiguous text paragraphs is supported. Refuse
    incomplete or structured content rather than silently dropping it from
    a replacement or a freshness comparison. No request is sent here.
    """
    try:
        if raw.get('suggestionsViewMode') != 'SUGGESTIONS_INLINE':
            raise ValueError('Docs response must explicitly use SUGGESTIONS_INLINE')
        _no_suggestions(raw)
        document_id, revision = _label(raw['documentId']), _label(raw['revisionId'])
        tabs = raw['tabs']
        if not isinstance(tabs, list) or len(tabs) != 1 or tabs[0].get('childTabs'):
            raise ValueError('Exactly one tab without child tabs is required')
        tab = tabs[0]
        tab_id = _label(tab['tabProperties']['tabId'])
        doc = tab['documentTab']
        if any(doc.get(k) for k in ('headers', 'footers', 'footnotes', 'inlineObjects', 'positionedObjects')):
            raise ValueError('Only a plain-text body is supported')
        blocks = doc['body']['content']
        if not isinstance(blocks, list) or len(blocks) < 2:
            raise ValueError('Complete body including section break is required')
        first = blocks[0]
        if set(first) - {'startIndex', 'endIndex', 'sectionBreak'} or 'sectionBreak' not in first:
            raise ValueError('Missing initial section break')
        if first.get('startIndex', 0) != 0 or first['endIndex'] != 1:
            raise ValueError('Invalid initial section range')
        cursor, pieces = 1, []
        for block in blocks[1:]:
            if set(block) - {'startIndex', 'endIndex', 'paragraph'}:
                raise ValueError('Unsupported body structure')
            if type(block['startIndex']) is not int or block['startIndex'] != cursor:
                raise ValueError('Incomplete paragraph range')
            paragraph = block['paragraph']
            if set(paragraph) - {'elements', 'paragraphStyle'}:
                raise ValueError('Unsupported paragraph structure')
            elements = paragraph['elements']
            if not isinstance(elements, list) or not elements:
                raise ValueError('Missing text elements')
            paragraph_text = []
            for element in elements:
                if set(element) - {'startIndex', 'endIndex', 'textRun'}:
                    raise ValueError('Only text runs are supported')
                run = element['textRun']
                if set(run) - {'content', 'textStyle'}:
                    raise ValueError('Unsupported text run')
                text = _text(run['content'])
                if not text or type(element['startIndex']) is not int or element['startIndex'] != cursor:
                    raise ValueError('Incomplete text range')
                cursor += _utf16_length(text)
                if type(element['endIndex']) is not int or element['endIndex'] != cursor:
                    raise ValueError('Invalid UTF-16 text range')
                paragraph_text.append(text)
            content = ''.join(paragraph_text)
            if not content.endswith('\n') or type(block['endIndex']) is not int or block['endIndex'] != cursor:
                raise ValueError('Incomplete paragraph')
            pieces.append(content)
        return DocsSnapshot(document_id, tab_id, revision, ''.join(pieces))
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('Incomplete or unsupported Docs response') from exc


def plan_update(bundle: Bundle, remote: DocsSnapshot, binding: DocsBinding) -> UpdatePlan:
    """Build, but never execute, one revision-guarded full-body update.

    Destination identity and previous readback hash must match before replacing
    anything. Never adopt a manual edit as the new baseline automatically.
    Clear-to-empty and sourceless publications are unsupported, even as no-ops.
    """
    if type(bundle.source_count) is not int or bundle.source_count < 1:
        raise ValueError('Bundle requires a positive source_count')
    if not _text(bundle.text).strip():
        raise ValueError('Bundle requires nonempty publication text')
    _label(remote.revision_id)
    if (remote.document_id, remote.tab_id) != (binding.document_id, binding.tab_id):
        raise ValueError('Destination identity mismatch')
    if _digest(_text(remote.text)) != binding.last_verified_sha256:
        raise ValueError('Remote text changed since the last verified publication')
    if not remote.text.endswith('\n') or not bundle.text.endswith('\n'):
        raise ValueError('Document body must retain its final newline')
    if _digest(_text(bundle.text)) != bundle.sha256:
        raise ValueError('Bundle digest mismatch')
    body = None
    action = 'unchanged'
    if remote.text != bundle.text:
        action = 'replace_text'
        requests = []
        # Google indexes are UTF-16 units. The final body newline is undeletable.
        end = _utf16_length(remote.text)
        if end > 1:
            requests.append({'deleteContentRange': {'range': {
                'tabId': remote.tab_id, 'startIndex': 1, 'endIndex': end,
            }}})
        requests.append({'insertText': {
            'location': {'tabId': remote.tab_id, 'index': 1}, 'text': bundle.text[:-1],
        }})
        body = {'writeControl': {'requiredRevisionId': remote.revision_id}, 'requests': requests}
    return UpdatePlan(action, remote.document_id, remote.tab_id, bundle.text, bundle.sha256, body)


def verify_readback(plan: UpdatePlan, remote: DocsSnapshot) -> str:
    """Verify only destination text identity; proves neither upload nor NLM freshness."""
    if (remote.document_id, remote.tab_id) != (plan.document_id, plan.tab_id):
        raise ValueError('Readback destination mismatch')
    if remote.text != plan.expected_text or _digest(remote.text) != plan.expected_sha256:
        raise ValueError('Readback content mismatch')
    return plan.expected_sha256
