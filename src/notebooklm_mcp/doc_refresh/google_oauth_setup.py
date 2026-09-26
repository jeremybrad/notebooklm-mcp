"""Explicit operator setup only; no automatic consent or credential repair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .google_keychain import KeychainStore, KeychainError, KEYCHAIN_ERROR_CODES
from .google_oauth import OAuthClient, OAuthError, StoredGrant, ERROR_CODES
from .oauth_loopback import get_authorization_code, LoopbackError
from .publication_credentials import (ProviderError, PROVIDER_CODES, check_grant, load_config,
                                      load_desktop_client)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('diagnose', 'enroll', 'renew'))
    parser.add_argument('--config', required=True, type=Path,
                        help='Explicit nonsecret publisher configuration')
    parser.add_argument('--client-config', type=Path,
                        help='Setup only: private downloaded Desktop OAuth client JSON')
    args = parser.parse_args(argv)
    if (args.mode == 'diagnose') == bool(args.client_config):
        parser.error('enroll/renew require --client-config; diagnose forbids it')
    failure = None
    try:
        config = load_config(args.config)
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
    except LoopbackError:
        failure = 'consent_callback_failed'
    except (KeyboardInterrupt, EOFError):
        failure = 'oauth_setup_cancelled'
    except Exception:
        failure = 'oauth_setup_failed'
    # No raw exception, callback URL, code, client secret or token is printed.
    print(failure, file=sys.stderr)
    return 130 if failure == 'oauth_setup_cancelled' else 1


if __name__ == '__main__':
    raise SystemExit(main())
