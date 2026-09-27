"""Explicit cohort boundaries, with fictional repositories and no cloud calls."""
import hashlib
import json
from pathlib import Path

import pytest

from notebooklm_mcp.doc_refresh import publication_cohort as cohort
from notebooklm_mcp.doc_refresh.manifest import DEFAULT_MANIFEST_PATH
from tests.test_source_bundle import repo, git, commit


@pytest.fixture
def configured(repo, tmp_path):
    origin = 'https://github.com/example/fictional.git'
    git(repo, 'remote', 'add', 'origin', origin)
    git(repo, 'update-ref', 'refs/remotes/origin/main', git(repo, 'rev-parse', 'HEAD'))
    manifest = tmp_path / 'manifest.yaml'
    manifest.write_bytes(DEFAULT_MANIFEST_PATH.read_bytes())
    data = {'version': 1, 'manifest': {'path': str(manifest),
            'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
            'repositories': [{'root': str(repo), 'name': repo.name,
                              'origin': origin, 'branch': 'refs/heads/main'}]}
    path = tmp_path / 'cohort.json'
    path.write_text(json.dumps(data))
    return path, data, repo


def test_offline_snapshot_fixes_manifest_and_revisions(configured, monkeypatch):
    path, data, repo = configured
    old = git(repo, 'rev-parse', 'HEAD')
    with cohort.prepare(path) as prepared:
        assert prepared.freshness == 'unverified-local-ref'
        assert prepared.jobs[0].revision == old
        original = prepared.manifest.read_bytes()
        Path(data['manifest']['path']).write_text('changed')
        (repo / 'code.py').write_text('new')
        new = commit(repo)
        git(repo, 'update-ref', 'refs/remotes/origin/main', new)
        assert prepared.manifest.read_bytes() == original
        assert prepared.jobs[0].revision == old
    assert not prepared.manifest.exists()


@pytest.mark.parametrize('mutation', ['duplicate', 'wseries', 'origin', 'branch', 'manifest', 'extra', 'alias'])
def test_invalid_cohort_refused(configured, mutation):
    path, data, repo = configured
    if mutation == 'duplicate':
        data['repositories'] *= 2
    elif mutation == 'wseries':
        data['repositories'][0]['name'] = 'W007_private'
    elif mutation == 'origin':
        data['repositories'][0]['origin'] = 'ext::sh -c bad'
    elif mutation == 'branch':
        data['repositories'][0]['branch'] = 'refs/heads/main~1'
    elif mutation == 'manifest':
        Path(data['manifest']['path']).write_text('changed')
    elif mutation == 'extra':
        data['execute'] = 'untrusted'
    else:
        alias = repo.parent / 'alias'
        alias.symlink_to(repo, target_is_directory=True)
        data['repositories'][0]['root'] = str(alias)
    path.write_text(json.dumps(data))
    with pytest.raises(cohort.CohortError):
        with cohort.prepare(path):
            pytest.fail('invalid cohort accepted')


def test_fetch_failure_does_not_use_stale_ref(configured, monkeypatch):
    path, _, _ = configured
    real = cohort._git
    def fail(root, *args):
        if 'fetch' in args:
            raise cohort.CohortError('fetch_failed')
        return real(root, *args)
    monkeypatch.setattr(cohort, '_git', fail)
    with pytest.raises(cohort.CohortError, match='fetch_failed'):
        with cohort.prepare(path, fetch=True):
            pytest.fail('stale ref accepted')


def test_duplicate_json_key_refused(configured):
    path, _, _ = configured
    path.write_text('{"version":1,"version":1}')
    with pytest.raises(cohort.CohortError):
        with cohort.prepare(path):
            pytest.fail('duplicate key accepted')


def test_non_regular_config_is_refused_without_blocking(tmp_path):
    import os
    pipe = tmp_path / 'cohort.json'
    os.mkfifo(pipe)
    with pytest.raises(cohort.CohortError, match='unsafe_configuration_path'):
        with cohort.prepare(pipe):
            pytest.fail('pipe accepted')


def test_fetch_uses_explicit_origin_and_refspec(configured, monkeypatch):
    path, data, root = configured
    calls = []
    real = cohort._git
    def recorded(root, *args):
        if 'fetch' in args:
            calls.append(args)
            return ''
        return real(root, *args)
    monkeypatch.setattr(cohort, '_git', recorded)
    with cohort.prepare(path, fetch=True) as prepared:
        assert prepared.freshness == 'fetched-origin'
    assert calls == [('fetch', '--no-tags', '--no-recurse-submodules',
                      '--no-write-fetch-head', '--', data['repositories'][0]['origin'],
                      'refs/heads/main:refs/remotes/origin/main')]


def test_git_child_drops_routing_environment(configured, monkeypatch):
    from types import SimpleNamespace
    path, _, root = configured
    monkeypatch.setenv('GIT_CONFIG_COUNT', '9')
    monkeypatch.setenv('GIT_SSH_COMMAND', 'untrusted-command')
    monkeypatch.setenv('GIT_DIR', '/untrusted/repository')
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=b'')
    monkeypatch.setattr(cohort.subprocess, 'run', run)
    cohort._git(root, 'check-ref-format', 'refs/heads/main')
    command, options = calls[0]
    assert not {'GIT_CONFIG_COUNT', 'GIT_SSH_COMMAND', 'GIT_DIR'} & options['env'].keys()
    assert options['env']['GIT_TERMINAL_PROMPT'] == '0'
    assert 'core.hooksPath=/dev/null' in command
    assert options['timeout'] == 120
    assert options['check'] is True
