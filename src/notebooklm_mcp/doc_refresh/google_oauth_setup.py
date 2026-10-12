"""Explicit operator setup only; no automatic consent or credential repair."""
from __future__ import annotations

import argparse
import hmac
import json
from pathlib import Path
import sys

from .google_keychain import KeychainStore, KeychainError, KEYCHAIN_ERROR_CODES
from .google_oauth import OAuthClient, OAuthError, StoredGrant, ERROR_CODES, _picker_file_id
from .oauth_loopback import get_authorization_code, get_file_authorization_code, LoopbackError
from .publication_credentials import (ProviderError, PROVIDER_CODES, check_grant, load_config,
                                      load_desktop_client)


class _PersistenceUnknown(Exception):
    """A credential write was attempted; no rollback or automatic retry."""


def _select_file(config, file_id: str) -> int:
    _picker_file_id(file_id)
    store = KeychainStore(config.selection)
    previous = store.read(interactive=False)
    previous_grant = StoredGrant.parse(previous)
    check_grant(config, previous_grant)
    client = previous_grant.client
    if not client.client_secret:
        raise ProviderError('grant_invalid')
    code, redirect_uri, verifier = get_file_authorization_code(client, file_id=file_id)
    with OAuthClient() as oauth:
        received = oauth.exchange_code(client, code, redirect_uri, verifier, config.email)
    if not isinstance(received, StoredGrant):
        raise ProviderError('grant_invalid')
    grant = StoredGrant.parse(received.serialize())
    check_grant(config, grant)
    if grant.client != client or grant.account != previous_grant.account:
        raise ProviderError('grant_mismatch')
    print(json.dumps({'status': 'file_selection_received_not_stored',
                      'email': grant.account.email_address,
                      'permission_id': grant.account.permission_id,
                      'client_id': grant.client.client_id, 'file_id': file_id}))
    answer = input('To update this existing grant, type the displayed email and file ID separated by one space: ')
    if answer != grant.account.email_address + ' ' + file_id:
        print('Selection grant not stored; Google-side consent is not rolled back', file=sys.stderr)
        return 1
    payload = grant.serialize()
    try:
        store.update(previous, payload, interactive=False)
    except KeychainError as error:
        if error.code == 'conflict':
            raise
        raise _PersistenceUnknown() from None
    except (Exception, KeyboardInterrupt):
        raise _PersistenceUnknown() from None
    try:
        if not hmac.compare_digest(store.read(interactive=False), payload):
            raise _PersistenceUnknown()
    except (Exception, KeyboardInterrupt):
        raise _PersistenceUnknown() from None
    print(json.dumps({'status': 'file_selection_grant_stored',
                      'email': grant.account.email_address, 'file_id': file_id,
                      'next': 'Separately authorize native file verification; no publication performed'}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('diagnose', 'enroll', 'renew', 'select-file'))
    parser.add_argument('--config', required=True, type=Path,
                        help='Explicit nonsecret publisher configuration')
    parser.add_argument('--client-config', type=Path,
                        help='Setup only: private downloaded Desktop OAuth client JSON')
    parser.add_argument('--file-id', help='select-file only: exact one existing Drive file')
    args = parser.parse_args(argv)
    if args.mode == 'select-file':
        if args.client_config or args.file_id is None:
            parser.error('select-file requires --file-id and forbids --client-config')
    elif args.file_id is not None:
        parser.error('--file-id is only for select-file')
    elif (args.mode == 'diagnose') == bool(args.client_config):
        parser.error('enroll/renew require --client-config; diagnose forbids it')
    failure = None
    try:
        if args.mode == 'select-file':
            _picker_file_id(args.file_id)
        config = load_config(args.config, live=args.mode == 'select-file')
        if args.mode == 'select-file':
            return _select_file(config, args.file_id)
        if args.mode == 'diagnose':
            print(json.dumps({'status': 'configuration_valid', 'credential_access': False,
                              'account_pinned': config.permission_id is not None,
                              'destination_count': len(config.destinations)}))
            return 0
        client = load_desktop_client(args.client_config)
        if client.client_id != config.client_id:
            raise ProviderError('grant_mismatch')
        store = KeychainStore(config.selection)
        previous = previous_grant = None
        if args.mode == 'renew':
            previous = store.read(interactive=True)
            previous_grant = StoredGrant.parse(previous)
            check_grant(config, previous_grant, require_pin=False)
        code, redirect_uri, verifier = get_authorization_code(client)
        with OAuthClient() as oauth:
            grant = oauth.exchange_code(client, code, redirect_uri, verifier, config.email)
        check_grant(config, grant, require_pin=False)
        if previous_grant is not None and grant.account != previous_grant.account:
            raise ProviderError('grant_mismatch')
        print(json.dumps({'status': 'consent_received_not_stored',
                          'email': grant.account.email_address,
                          'permission_id': grant.account.permission_id,
                          'client_id': grant.client.client_id}))
        answer = input('To store this grant, type the displayed email address: ')
        if answer != grant.account.email_address:
            print('Enrollment cancelled; grant not stored', file=sys.stderr)
            return 1
        if previous is None:
            store.create(grant.serialize(), interactive=True)
        else:
            store.update(previous, grant.serialize(), interactive=True)
        print(json.dumps({'status': 'grant_stored', 'email': grant.account.email_address,
                          'permission_id': grant.account.permission_id,
                          'next': 'Pin this permission_id in config before publication'}))
        return 0
    except ProviderError as error:
        failure = 'configuration_' + error.code if error.code in PROVIDER_CODES else 'configuration_invalid'
    except KeychainError as error:
        failure = 'keychain_' + error.code if error.code in KEYCHAIN_ERROR_CODES else 'keychain_unavailable'
    except OAuthError as error:
        failure = 'oauth_' + error.code if error.code in ERROR_CODES else 'oauth_failed'
    except LoopbackError as error:
        failure = error.code if args.mode == 'select-file' else 'consent_callback_failed'
    except _PersistenceUnknown:
        failure = 'credential_persistence_unknown'
    except (KeyboardInterrupt, EOFError):
        failure = 'oauth_setup_cancelled'
    except Exception:
        failure = 'oauth_setup_failed'
    # No raw exception, callback URL, code, client secret or token is printed.
    print(failure, file=sys.stderr)
    return 130 if failure == 'oauth_setup_cancelled' else 1


if __name__ == '__main__':
    raise SystemExit(main())
