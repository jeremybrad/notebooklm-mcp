"""Read-only status of original documents from explicit local evidence."""
from datetime import datetime, timezone
import argparse
import json
import re
from pathlib import Path

from .individual_publication import KEY, digest
from .publication_state import MapStore
from .source_bundle import build_bundle

FORMAT = 'c021.individual-publication-batch.v1'


def _time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Aware timestamp required')
    return parsed.astimezone(timezone.utc)


def reduce_status(selected, notebooks, receipts, *, now, stale_after_seconds=None):
    """Pure reducer. No threshold, observation timestamp or schedule is inferred."""
    clock = _time(now)
    if stale_after_seconds is not None and (stale_after_seconds <= 0):
        raise ValueError('Positive explicit stale threshold required')
    runs = []
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError('Invalid receipt')
        if receipt.get('format') != FORMAT or receipt.get('mode') not in {'publish', 'reconcile'}:
            continue
        if (not isinstance(receipt.get('items'), list)
                or any(not isinstance(i, dict) for i in receipt['items'])
                or receipt.get('status') not in {'success', 'failed'}):
            raise ValueError('Invalid publication receipt')
        stamp = _time(receipt['completed_at'])
        if stamp > clock:
            raise ValueError('Future receipt')
        runs.append((stamp, receipt))
    runs.sort(key=lambda pair: (pair[0], pair[1].get('run_id', '')))
    targets = {(s['repo'], s['path']): s for s in selected}
    for repo, record in notebooks.items():
        for path in record.get(KEY, {}):
            targets.setdefault((repo, path), None)
    rows = []
    for (repo, path), target in sorted(targets.items()):
        record = notebooks.get(repo, {})
        entry = record.get(KEY, {}).get(path)
        history = [(stamp, run, item) for stamp, run in runs for item in run.get('items', [])
                   if item.get('repo') == repo and item.get('path') == path]
        relevant_runs = [(stamp, run) for stamp, run in runs
                         if any(i.get('repo') == repo for i in run.get('items', []))]
        latest = history[-1] if history else None
        successes = [h for h in history if h[2].get('status') == 'success'
                     and h[2].get('verification') == 'remote']
        last_success = successes[-1][1]['completed_at'] if successes else None
        publication = 'unknown'
        observation = 'unknown'
        problems = []
        if target is None:
            problems.append('original_missing_from_selection')
        if entry is None:
            problems.append('binding_missing')
        else:
            verified = entry['verified']
            publication = 'recorded_verified' if verified['source'] else 'unknown'
            if target and verified['sha256'] != target['sha256']:
                publication = 'changed'
                problems.append('publication_needed')
            if entry['pending']:
                problems.append('pending_reconciliation')
            observed = entry['notebook']
            if observed:
                observation = ('recorded_hash_match' if target and observed['sha256'] == target['sha256']
                               else 'stale')
                if observation == 'stale':
                    problems.append('notebook_observation_stale')
        if latest and (latest[2].get('status') != 'success' or latest[1].get('status') != 'success'):
            problems.append('latest_run_failed_or_partial')
        if relevant_runs and relevant_runs[-1][1].get('status') != 'success':
            if 'latest_run_failed_or_partial' not in problems:
                problems.append('latest_run_failed_or_partial')
        if any(run.get('status') != 'success' and not run.get('items') for _, run in runs):
            problems.append('unattributed_preflight_failure')
        if not history:
            problems.append('receipt_missing')
        freshness = 'unknown'
        if last_success and stale_after_seconds is not None:
            freshness = ('stale' if (clock - _time(last_success)).total_seconds() > stale_after_seconds
                         else 'within_explicit_bound')
            if freshness == 'stale':
                problems.append('publication_receipt_stale')
        if observation == 'unknown':
            problems.append('notebook_observation_missing')
        rows.append({'repo': repo, 'path': path, 'file_id': entry['file_id'] if entry else None,
                     'notebook_id': record.get('notebook_id'),
                     'source_id': entry['notebook']['source_id'] if entry and entry['notebook'] else None,
                     'target': target, 'verified': entry['verified'] if entry else None,
                     'pending': entry['pending'] if entry else None,
                     'publication': publication, 'notebook_observation': observation,
                     'observation_evidence_at': None,
                     'observation_evidence': entry['notebook']['evidence'] if entry and entry['notebook'] else None,
                     'last_successful_publication_at': last_success,
                     'last_successful_scheduled_run_at': None,
                     'receipt_freshness': freshness, 'problems': problems,
                     'next_owner': 'operator',
                     'next_action': ('Preserve original inputs; inspect pending intent before any retry.'
                                     if 'pending_reconciliation' in problems else
                                     'Inspect affected original and local evidence; obtain a bounded source observation.'
                                     if problems else 'Confirm observation mode and timestamp before claiming current usability.')})
    return {'format': 'c021.individual-status.v1', 'verification': 'local-recorded-only',
            'evaluated_at': now, 'stale_after_seconds': stale_after_seconds,
            'aggregate': 'attention' if any(r['problems'] for r in rows) else 'unknown',
            'canonical_doc_review': 'unknown', 'host_job_health': 'unknown',
            'older_artifact_state': 'unknown', 'items': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', nargs=2, action='append', required=True, metavar=('PATH', 'FULL_COMMIT'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--map', type=Path, required=True, dest='map_path')
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--now', required=True, help='Explicit aware evaluation timestamp')
    parser.add_argument('--stale-after-seconds', type=int)
    args = parser.parse_args(argv)
    try:
        if (len({str(Path(p).resolve()) for p, _ in args.repo}) != len(args.repo)
                or len({Path(p).name for p, _ in args.repo}) != len(args.repo)):
            raise ValueError('Unique repositories required')
        selected = []
        for path, revision in args.repo:
            if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
                raise ValueError('Full immutable commit required')
            bundle = build_bundle(Path(path), revision, manifest_path=args.manifest)
            selected.extend({'repo': source.repo, 'path': source.path,
                             'commit': bundle.receipt['commit'], 'blob_oid': source.source_revision,
                             'sha256': digest(source.text.encode('utf-8'))} for source in bundle.documents)
        # Read each explicitly selected receipt directory; never create a receipt or map.
        receipts = []
        for p in sorted(args.receipts.glob('*.json')):
            if p.stat().st_size > 4 * 1024 * 1024:
                raise ValueError('Oversize receipt')
            value = json.loads(p.read_text())
            if not isinstance(value, dict):
                raise ValueError('Invalid receipt')
            receipts.append(value)
        if not args.receipts.is_dir():
            raise ValueError('Missing receipt directory')
        result = reduce_status(selected, MapStore(args.map_path).read().data['notebooks'], receipts,
                               now=args.now, stale_after_seconds=args.stale_after_seconds)
    except (OSError, ValueError, KeyError, TypeError):
        print('Invalid or unavailable local status inputs')
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
