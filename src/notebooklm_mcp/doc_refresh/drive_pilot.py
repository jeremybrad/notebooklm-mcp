"""Run only the built-in synthetic Drive planning example; never perform I/O.

The CLI prints to stdout. It accepts no source paths, account, destination,
credentials or apply flag. Real integration must use the accepted source manifest.
"""
import argparse
from dataclasses import asdict
import hashlib
import json

from .drive_publication import (
    DocsBinding, SourceText, parse_document, plan_update, render_bundle, verify_readback,
)


def _synthetic_snapshot(text: str, revision: str) -> dict:
    cursor = 1
    content = [{'endIndex': 1, 'sectionBreak': {}}]
    for line in text.split('\n')[:-1]:
        paragraph = line + '\n'
        end = cursor + len(paragraph.encode('utf-16-le')) // 2
        content.append({'startIndex': cursor, 'endIndex': end, 'paragraph': {'elements': [
            {'startIndex': cursor, 'endIndex': end, 'textRun': {'content': paragraph}},
        ]}})
        cursor = end
    return {'documentId': 'synthetic-document-not-a-live-destination', 'revisionId': revision,
            'suggestionsViewMode': 'SUGGESTIONS_INLINE',
            'tabs': [{'tabProperties': {'tabId': 'synthetic-tab'},
                      'documentTab': {'body': {'content': content}}}]}


def build_pilot() -> dict:
    """Demonstrate deterministic planning and synthetic readback, not an upload."""
    bundle = render_bundle('Journal explanation — SYNTHETIC EXAMPLE', [
        SourceText('C003_synthetic', 'docs/inputs.md', 'a' * 40,
                   '# Example upstream products\n\nConversation summaries and an activity timeline.\n'),
        SourceText('C014_synthetic', 'docs/journal.md', 'b' * 40,
                   '# Example journal assembly\n\nCombine inputs with narrative context. '
                   'Label missing evidence and explain later enrichment.\n'),
    ])
    remote = parse_document(_synthetic_snapshot('\n', 'synthetic-revision-1'))
    binding = DocsBinding(remote.document_id, remote.tab_id, hashlib.sha256(b'\n').hexdigest())
    plan = plan_update(bundle, remote, binding)
    # This is an explicitly constructed fixture, not a response from Google.
    readback = parse_document(_synthetic_snapshot(bundle.text, 'synthetic-revision-2'))
    verified_hash = verify_readback(plan, readback)
    repeat = plan_update(bundle, readback, DocsBinding(remote.document_id, remote.tab_id, verified_hash))
    return {
        'mode': 'synthetic_offline', 'network_requests_sent': 0,
        'source_selection': 'built_in_synthetic_text_only',
        'google_docs_publication': 'not_attempted', 'notebooklm_freshness': 'not_checked',
        'artifact_generation': 'not_attempted', 'bundle': asdict(bundle),
        'plan': asdict(plan), 'synthetic_readback_sha256': verified_hash,
        'repeat_action': repeat.action,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    result = build_pilot()
    if args.format == 'markdown':
        print(result['bundle']['text'], end='')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
