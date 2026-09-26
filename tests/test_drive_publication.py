"""Synthetic tests; no repository discovery, credentials or Google calls."""
import copy
import hashlib

import pytest

from notebooklm_mcp.doc_refresh.drive_publication import (
    Bundle, DocsBinding, SourceText, parse_document, plan_update, render_bundle, verify_readback,
)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def document(text='\n', revision='r1', document_id='synthetic-doc', tab_id='t1'):
    end = 1 + len(text.encode('utf-16-le')) // 2
    return {'documentId': document_id, 'revisionId': revision,
            'suggestionsViewMode': 'SUGGESTIONS_INLINE', 'tabs': [{
        'tabProperties': {'tabId': tab_id}, 'documentTab': {'body': {'content': [
            {'endIndex': 1, 'sectionBreak': {}},
            {'startIndex': 1, 'endIndex': end, 'paragraph': {'elements': [
                {'startIndex': 1, 'endIndex': end, 'textRun': {'content': text}}
            ]}},
        ]}},
    }]}


def source(path='README.md', content='# Example\nSynthetic content.\n'):
    return SourceText('C021_example', path, 'a' * 40, content)


def binding(text='\n'):
    return DocsBinding('synthetic-doc', 't1', digest(text))


def test_bundle_stable_order_normalized_newlines_and_change_identity():
    a, b = source(), source('docs/flow.md', 'First\r\nSecond\r\n')
    first = render_bundle('Example', [b, a])
    second = render_bundle('Example', [a, source('docs/flow.md', 'First\nSecond\n')])
    assert first == second
    assert first.source_count == 2
    assert 'C021_example/README.md' in first.text
    assert 'a' * 40 in first.text
    assert render_bundle('Example', [a]).sha256 != first.sha256
    assert render_bundle('Example', [source(content='changed')]).sha256 != first.sha256
    assert render_bundle('Renamed', [a, b]).sha256 != first.sha256


def test_bundle_requires_nonempty_unique_sources_and_revision():
    with pytest.raises(ValueError):
        render_bundle('Example', [])
    with pytest.raises(ValueError):
        render_bundle('Example', [source(), source()])
    with pytest.raises(ValueError):
        render_bundle('Example', [SourceText('C021_example', 'README.md', 'main', 'text')])


@pytest.mark.parametrize('content', ['bad\x00text', 'bad\x0ctext', '\ue000', '\ud800'])
def test_bundle_rejects_stripped_characters_and_unpaired_surrogates(content):
    with pytest.raises(ValueError):
        render_bundle('Example', [source(content=content)])


def test_plan_preserves_identity_revision_and_final_newline():
    bundle = render_bundle('Example', [source(content='Unicode 🐝')])
    old = 'Old 🐝\n'
    plan = plan_update(bundle, parse_document(document(old)), binding(old))
    assert plan.action == 'replace_text'
    assert plan.document_id == 'synthetic-doc'
    assert plan.body['writeControl'] == {'requiredRevisionId': 'r1'}
    assert plan.body['requests'][0]['deleteContentRange']['range'] == {
        'tabId': 't1', 'startIndex': 1, 'endIndex': len(old.encode('utf-16-le')) // 2,
    }
    insert = plan.body['requests'][1]['insertText']
    assert insert['location'] == {'tabId': 't1', 'index': 1}
    assert insert['text'] + '\n' == bundle.text
    assert verify_readback(plan, parse_document(document(bundle.text, revision='r2'))) == bundle.sha256
    assert plan_update(bundle, parse_document(document(bundle.text)), binding(bundle.text)).action == 'unchanged'


def test_empty_doc_only_inserts_and_noop_has_no_requests():
    bundle = render_bundle('Example', [source()])
    plan = plan_update(bundle, parse_document(document()), binding())
    assert len(plan.body['requests']) == 1
    noop = plan_update(bundle, parse_document(document(bundle.text)), binding(bundle.text))
    assert noop.body is None


def test_remote_manual_change_and_wrong_destination_refuse():
    bundle = render_bundle('Example', [source()])
    for remote in [document('Manual edit\n'), document(document_id='wrong'), document(tab_id='wrong')]:
        with pytest.raises(ValueError):
            plan_update(bundle, parse_document(remote), binding())
    plan = plan_update(bundle, parse_document(document()), binding())
    for remote in [document(), document(bundle.text, document_id='wrong'), document(bundle.text, tab_id='wrong')]:
        with pytest.raises(ValueError):
            verify_readback(plan, parse_document(remote))


@pytest.mark.parametrize('mutation', [
    lambda d: d.pop('revisionId'),
    lambda d: d.pop('tabs'),
    lambda d: d['tabs'].append(copy.deepcopy(d['tabs'][0])),
    lambda d: d['tabs'][0].update(childTabs=[{}]),
    lambda d: d['tabs'][0]['documentTab']['body']['content'].append({'table': {}}),
    lambda d: d['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0].update(inlineObjectElement={}),
    lambda d: d['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0].update(suggestedInsertionIds=['x']),
    lambda d: d['tabs'][0]['documentTab']['body']['content'][1].update(endIndex=999),
    lambda d: d['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0].update(startIndex=2),
])
def test_unsupported_or_incomplete_google_document_refuses(mutation):
    raw = document('Hello\n')
    mutation(raw)
    with pytest.raises(ValueError):
        parse_document(raw)


def test_parse_unicode_and_multiple_paragraphs():
    raw = document('🐝\n')
    raw['tabs'][0]['documentTab']['body']['content'].append({
        'startIndex': 4, 'endIndex': 8,
        'paragraph': {'elements': [{'startIndex': 4, 'endIndex': 8, 'textRun': {'content': 'Two\n'}}]},
    })
    assert parse_document(raw).text == '🐝\nTwo\n'


def apply_requests(plan, raw):
    """Independent tiny fake of the two supported API operations, using UTF-16."""
    state = parse_document(raw)
    if plan.body['writeControl']['requiredRevisionId'] != state.revision_id:
        raise ValueError('Revision conflict')
    data = state.text.encode('utf-16-le')
    for request in plan.body['requests']:
        if 'deleteContentRange' in request:
            span = request['deleteContentRange']['range']
            assert span['tabId'] == state.tab_id
            start, end = (span['startIndex'] - 1) * 2, (span['endIndex'] - 1) * 2
            assert end <= len(data) - 2  # Never remove the final body newline.
            data = data[:start] + data[end:]
        else:
            insert = request['insertText']
            assert insert['location']['tabId'] == state.tab_id
            pos = (insert['location']['index'] - 1) * 2
            data = data[:pos] + insert['text'].encode('utf-16-le') + data[pos:]
    return document(data.decode('utf-16-le'), revision='r2')


@pytest.mark.parametrize('old', ['\n', 'Old\n', '🐝\nOther text\n'])
def test_update_requests_actually_produce_expected_content_and_stable_rerun(old):
    bundle = render_bundle('Synthetic', [source(content='New 🐝\n')])
    plan = plan_update(bundle, parse_document(document(old)), binding(old))
    readback = parse_document(apply_requests(plan, document(old)))
    assert verify_readback(plan, readback) == bundle.sha256
    assert plan_update(bundle, readback, binding(bundle.text)).body is None
    with pytest.raises(ValueError, match='Revision conflict'):
        apply_requests(plan, document(old, revision='concurrent-edit'))


def test_pilot_never_reads_sources_or_opens_network(monkeypatch):
    import builtins
    import socket
    from notebooklm_mcp.doc_refresh.drive_pilot import build_pilot

    def forbidden(*args, **kwargs):
        raise AssertionError('Offline pilot attempted external I/O')

    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    result = build_pilot()
    assert result['mode'] == 'synthetic_offline'
    assert result['network_requests_sent'] == 0
    assert result['notebooklm_freshness'] == 'not_checked'
    assert result['repeat_action'] == 'unchanged'
    assert result['bundle']['source_count'] == 2


@pytest.mark.parametrize('mode', [
    'PREVIEW_SUGGESTIONS_ACCEPTED', 'PREVIEW_WITHOUT_SUGGESTIONS',
    'DEFAULT_FOR_CURRENT_ACCESS', 'UNKNOWN', None, '',
])
@pytest.mark.parametrize('phase', ['planning', 'readback'])
def test_preview_or_ambiguous_view_cannot_enter_publication_flow(mode, phase):
    bundle = render_bundle('Synthetic', [source()])
    plan = plan_update(bundle, parse_document(document()), binding())
    raw = document() if phase == 'planning' else document(bundle.text, revision='r2')
    if mode is None:
        raw.pop('suggestionsViewMode')
    else:
        raw['suggestionsViewMode'] = mode
    with pytest.raises(ValueError, match='SUGGESTIONS_INLINE'):
        if phase == 'planning':
            plan_update(bundle, parse_document(raw), binding())
        else:
            verify_readback(plan, parse_document(raw))


@pytest.mark.parametrize('old', ['Old managed text\n', '\n'])
@pytest.mark.parametrize('text,count', [
    ('\n', 1), ('', 1), (' \t\n', 1), ('New\n', 0), ('New\n', -1),
    ('New\n', True), ('New\n', '1'),
])
def test_direct_empty_or_sourceless_bundle_refuses_before_any_plan(old, text, count):
    bundle = Bundle(text, digest(text), count)
    with pytest.raises(ValueError, match='nonempty publication|positive source_count'):
        plan_update(bundle, parse_document(document(old)), binding(old))


def test_soft_break_is_explicitly_unsupported_in_sources_and_remote_text():
    # U+000B is valid Google text, but outside this adapter's supported subset.
    with pytest.raises(ValueError, match='Unsupported'):
        render_bundle('Synthetic', [source(content='One\vTwo')])
    with pytest.raises(ValueError, match='Unsupported'):
        parse_document(document('One\vTwo\n'))


def test_empty_source_content_still_renders_a_nonempty_publication():
    bundle = render_bundle('Synthetic', [source(content='')])
    plan = plan_update(bundle, parse_document(document()), binding())
    assert plan.body['requests'][0]['insertText']['text']
    assert verify_readback(plan, parse_document(apply_requests(plan, document()))) == bundle.sha256
