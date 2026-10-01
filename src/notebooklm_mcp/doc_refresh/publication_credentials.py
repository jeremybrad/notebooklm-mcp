"""Explicit, nonsecret publisher configuration and a lazy credential factory.

Loading/diagnosing configuration performs no Keychain or Google operation.
Runtime access happens only after the batch has checked its sources and bindings.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Mapping

from .google_docs_transport import AccountExpectation, DestinationExpectation, GoogleDocsTransport
from .google_keychain import KeychainSelection, KeychainStore, KeychainError, KEYCHAIN_ERROR_CODES
from .google_oauth import DesktopClient, OAuthClient, OAuthError, StoredGrant, ERROR_CODES

MAX_CONFIG_BYTES = 65536
SERVICE = 'c021.notebooklm.google-data-oauth.v1'
PROVIDER_CODES = frozenset({'configuration_invalid', 'destination_unconfigured',
    'destination_mismatch', 'grant_mismatch', 'keychain_unavailable',
    'grant_invalid', 'refresh_failed'}) | frozenset('keychain_' + c for c in KEYCHAIN_ERROR_CODES) \
    | frozenset('oauth_' + c for c in ERROR_CODES)


class ProviderError(ValueError):
    def __init__(self, code: str):
        self.code = code if code in PROVIDER_CODES else 'configuration_invalid'
        super().__init__('Google credential provider: ' + self.code)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _bad_number(_):
    raise ValueError('nonfinite number')


def read_json(path: Path, *, private: bool = False):
    """Explicit bounded regular file only; parser/file exceptions are not exposed."""
    value, valid = None, False
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG_BYTES:
            raise ValueError('file shape')
        if private and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError('private file required')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError('file size')
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_number)
        valid = isinstance(value, dict)
    except Exception:
        pass
    finally:
        if fd is not None:
            os.close(fd)
    if not valid:
        raise ProviderError('configuration_invalid')
    return value


@dataclass(frozen=True)
class PublisherConfig:
    selection: KeychainSelection
    client_id: str
    email: str
    permission_id: str | None
    destinations: Mapping[str, DestinationExpectation]


def load_config(path: Path, *, live: bool = False) -> PublisherConfig:
    """No discovery/defaults for identity or destinations; null permission is setup-only."""
    value = read_json(path)
    config = None
    try:
        if set(value) != {'version', 'keychain_path', 'client_id', 'email',
                          'permission_id', 'destinations'} or type(value['version']) is not int \
                or value['version'] != 1:
            raise ValueError('schema')
        client = DesktopClient(value['client_id'])
        selection = KeychainSelection(Path(value['keychain_path']), SERVICE, value['email'])
        permission = value['permission_id']
        if permission is not None:
            AccountExpectation(permission, value['email'])
        if live and permission is None:
            raise ValueError('account pin required')
        if not isinstance(value['destinations'], dict) or len(value['destinations']) > 128:
            raise ValueError('destinations')
        destinations = {}
        for name, entry in value['destinations'].items():
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name) \
                    or not isinstance(entry, dict) or set(entry) != {'document_id', 'parent_id'}:
                raise ValueError('destination schema')
            destinations[name] = DestinationExpectation(**entry)
        config = PublisherConfig(selection, client.client_id, value['email'], permission,
                                 MappingProxyType(destinations))
    except Exception:
        pass
    if config is None:
        raise ProviderError('configuration_invalid')
    return config


def load_desktop_client(path: Path) -> DesktopClient:
    """Read Google's downloaded Desktop client config only on explicit setup."""
    value = read_json(path, private=True)
    client = None
    try:
        if set(value) != {'installed'} or not isinstance(value['installed'], dict):
            raise ValueError('Desktop client required')
        entry = value['installed']
        # Registered endpoint values must not redirect this fixed-endpoint client.
        if entry.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth' \
                or entry.get('token_uri') != 'https://oauth2.googleapis.com/token':
            raise ValueError('unexpected endpoint')
        # This setup lane consumes Google's Desktop client-secrets file format,
        # whose client_secret field is required. The lower-level OAuth protocol
        # model remains usable without a secret for nonsecret configuration.
        secret = entry['client_secret']
        if not isinstance(secret, str) or not secret:
            raise ValueError('Desktop client secret required')
        client = DesktopClient(entry['client_id'], secret)
    except Exception:
        pass
    if client is None:
        raise ProviderError('configuration_invalid')
    return client


def check_grant(config: PublisherConfig, grant: StoredGrant, *, require_pin=True):
    if (grant.client.client_id != config.client_id
            or grant.account.email_address != config.email
            or (require_pin and config.permission_id is None)
            or (config.permission_id is not None
                and grant.account.permission_id != config.permission_id)):
        raise ProviderError('grant_mismatch')


def transport_factory(config: PublisherConfig, *, individual=False, conditional_write_evidence=None):
    """Construct a lazy factory. No credential I/O until a specific job is entered."""
    @contextmanager
    def factory(job, document_id):
        if individual:
            from .individual_publication import document_key
            name = document_key(job.source)
        else:
            name = job.repo.absolute().name
        destination = config.destinations.get(name)
        if destination is None:
            raise ProviderError('destination_unconfigured')
        if destination.document_id != document_id:
            raise ProviderError('destination_mismatch')
        failure, grant, lease = None, None, None
        try:
            raw = KeychainStore(config.selection).read(interactive=False)
        except KeychainError as error:
            failure = 'keychain_' + error.code if error.code in KEYCHAIN_ERROR_CODES else 'keychain_unavailable'
        if failure:
            raise ProviderError(failure)
        try:
            grant = StoredGrant.parse(raw)
        except OAuthError:
            failure = 'grant_invalid'
        if failure:
            raise ProviderError(failure)
        check_grant(config, grant)
        try:
            with OAuthClient() as client:
                lease = client.refresh(grant)
        except OAuthError as error:
            failure = 'oauth_' + error.code if error.code in ERROR_CODES else 'refresh_failed'
        if failure:
            raise ProviderError(failure)
        if individual:
            from .google_markdown_transport import GoogleMarkdownTransport
            transport = GoogleMarkdownTransport(lease, grant.account, destination,
                conditional_write_evidence=conditional_write_evidence)
        else:
            transport = GoogleDocsTransport(lease, grant.account, destination)
        with transport as active:
            yield active
    return factory
