"""One explicitly selected file-based macOS login Keychain item.

Import and configuration validation do not load native libraries or open stores.
Only explicit read/create/update operations use Security.framework. No default
search list, environment lookup, keyring plugin, unlock, ACL edit or deletion.

Update compares expected bytes before SecItemUpdate under a process-local lock.
This is NOT cross-process compare-and-swap: provisioning/renewal must have an
exclusive writer. Native no-dialog behavior still needs separately authorized
host acceptance; synthetic tests do not establish unattended readiness.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hmac
from pathlib import Path
import sys
import threading
from typing import Any


SERVICE = 'c021.notebooklm.google-data-oauth.v1'
ACCOUNT = 'jeremybradford1977@gmail.com'
MAX_PAYLOAD_BYTES = 64 * 1024
KEYCHAIN_ERROR_CODES = frozenset({
    'invalid_configuration', 'invalid_payload', 'unsupported_platform',
    'native_unavailable', 'native_failure', 'not_found', 'already_exists',
    'access_denied', 'interaction_required', 'interaction_restore_failed',
    'keychain_unavailable', 'conflict',
})
_INTERACTION_LOCK = threading.Lock()
_INTERACTION_POISONED = False


class KeychainError(ValueError):
    """Fixed nonsecret error code. Native errors and values are never attached."""
    def __init__(self, code: str):
        self.code = code if code in KEYCHAIN_ERROR_CODES else 'native_failure'
        super().__init__('Google OAuth Keychain: ' + self.code)


@dataclass(frozen=True)
class KeychainSelection:
    """Operator-selected path; filename alone does not prove actual store identity."""
    path: Path
    service: str
    account: str

    def __post_init__(self):
        if (not isinstance(self.path, Path) or not self.path.is_absolute()
                or '..' in self.path.parts
                or self.path.name not in {'login.keychain', 'login.keychain-db'}
                or any(ord(char) < 32 or ord(char) == 127 for char in str(self.path))
                or self.service != SERVICE or self.account != ACCOUNT):
            raise KeychainError('invalid_configuration')


def _payload(value: Any) -> bytes:
    if type(value) is not bytes or not 0 < len(value) <= MAX_PAYLOAD_BYTES:
        raise KeychainError('invalid_payload')
    return value


def _error_code(error: Exception) -> str:
    return error.code if type(error) is KeychainError else 'native_failure'


class KeychainStore:
    """Exact item operations with a trusted synthetic backend injection seam.

    Runtime defaults to no interaction. Every operation saves the previous
    process-wide interaction setting, sets its explicit mode, then restores it.
    A restoration failure poisons this module's later operations until process
    restart. The lock coordinates users of this adapter, not unrelated native
    Keychain calls in other libraries or processes; use a dedicated runtime.
    """
    def __init__(self, selection: KeychainSelection, *, backend=None):
        if type(selection) is not KeychainSelection:
            raise KeychainError('invalid_configuration')
        self._selection = KeychainSelection(selection.path, selection.service, selection.account)
        if backend is None and sys.platform != 'darwin':
            raise KeychainError('unsupported_platform')
        self._backend = backend

    def read(self, *, interactive: bool = False) -> bytes:
        return self._perform('read', interactive=interactive)

    def create(self, payload: bytes, *, interactive: bool = False) -> None:
        self._perform('create', payload=_payload(payload), interactive=interactive)

    def update(self, expected: bytes, payload: bytes, *, interactive: bool = False) -> None:
        self._perform('update', expected=_payload(expected), payload=_payload(payload),
                      interactive=interactive)

    def _perform(self, operation: str, *, expected=None, payload=None, interactive=False):
        global _INTERACTION_POISONED
        if type(interactive) is not bool:
            raise KeychainError('invalid_configuration')
        failure, result = None, None
        with _INTERACTION_LOCK:
            if _INTERACTION_POISONED:
                raise KeychainError('interaction_restore_failed')
            previous, reference = None, None
            try:
                if self._backend is None:
                    self._backend = _SecurityBackend()
                previous = self._backend.get_interaction_allowed()
                if type(previous) is not bool:
                    previous = None
                    raise KeychainError('native_failure')
                self._backend.set_interaction_allowed(interactive)
                reference = self._backend.open_keychain(str(self._selection.path))
                if reference is None:
                    raise KeychainError('keychain_unavailable')
                args = (reference, self._selection.service, self._selection.account)
                if operation == 'read':
                    result = _payload(self._backend.read(*args))
                elif operation == 'create':
                    # SecItemAdd provides atomic duplicate refusal; never delete.
                    self._backend.create(*args, payload)
                else:
                    current = _payload(self._backend.read(*args))
                    if not hmac.compare_digest(current, expected):
                        raise KeychainError('conflict')
                    self._backend.update(*args, payload)
            except Exception as error:
                failure = _error_code(error)
            finally:
                if reference is not None:
                    try:
                        self._backend.release_keychain(reference)
                    except Exception:
                        failure = failure or 'native_failure'
                if previous is not None:
                    try:
                        # Restore even when the initial setter reported failure:
                        # the old global setting is known; its new state may not be.
                        self._backend.set_interaction_allowed(previous)
                    except Exception:
                        failure = 'interaction_restore_failed'
                        _INTERACTION_POISONED = True
        # No chained native exception carrying values, paths or query objects.
        if failure:
            raise KeychainError(failure)
        return result


def _status(status: int) -> None:
    if status:
        code = {
            -25300: 'not_found', -25299: 'already_exists',
            -25293: 'access_denied', -128: 'access_denied', -25292: 'access_denied',
            -25308: 'interaction_required', -25315: 'interaction_required',
            -25291: 'keychain_unavailable', -25294: 'keychain_unavailable',
            -25295: 'keychain_unavailable',
        }.get(status, 'native_failure')
        raise KeychainError(code)


def _constant(library, name: str) -> int:
    value = ctypes.c_void_p.in_dll(library, name).value
    if not value:
        raise KeychainError('native_unavailable')
    return value


def _callbacks(library, name: str) -> int:
    # Callback constants are structs (their address), unlike CFStringRef symbols
    # above, which are pointer variables (their value).
    return ctypes.addressof(ctypes.c_byte.in_dll(library, name))


class _SecurityBackend:
    """Small ctypes bridge; private injected framework objects support fake-native tests.

    Signatures follow the macOS SDK's SecKeychain.h, SecItem.h and CF headers.
    kSecMatchSearchList constrains lookup/update; kSecUseKeychain constrains add.
    Legacy file-Keychain UI is controlled by SecKeychainSetUserInteractionAllowed;
    data-protection-only no-UI query flags are intentionally not relied upon.
    """
    def __init__(self, *, _security=None, _core=None):
        if sys.platform != 'darwin':
            raise KeychainError('unsupported_platform')
        failure = False
        try:
            self.sec = _security if _security is not None else ctypes.CDLL(
                '/System/Library/Frameworks/Security.framework/Security')
            self.cf = _core if _core is not None else ctypes.CDLL(
                '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            self._bind()
            names = ('kSecClass', 'kSecClassGenericPassword', 'kSecAttrService',
                     'kSecAttrAccount', 'kSecMatchSearchList', 'kSecReturnData',
                     'kSecMatchLimit', 'kSecMatchLimitOne', 'kSecUseKeychain', 'kSecValueData')
            self.symbols = {name: _constant(self.sec, name) for name in names}
            self.true = _constant(self.cf, 'kCFBooleanTrue')
            self.array_callbacks = _callbacks(self.cf, 'kCFTypeArrayCallBacks')
            self.key_callbacks = _callbacks(self.cf, 'kCFTypeDictionaryKeyCallBacks')
            self.value_callbacks = _callbacks(self.cf, 'kCFTypeDictionaryValueCallBacks')
        except Exception:
            failure = True
        if failure:
            raise KeychainError('native_unavailable')

    def _bind(self):
        pointer, index = ctypes.c_void_p, ctypes.c_long
        signatures = {
            'SecKeychainOpen': ([ctypes.c_char_p, ctypes.POINTER(pointer)], ctypes.c_int32),
            'SecKeychainGetUserInteractionAllowed': ([ctypes.POINTER(ctypes.c_ubyte)], ctypes.c_int32),
            'SecKeychainSetUserInteractionAllowed': ([ctypes.c_ubyte], ctypes.c_int32),
            'SecItemCopyMatching': ([pointer, ctypes.POINTER(pointer)], ctypes.c_int32),
            'SecItemAdd': ([pointer, ctypes.POINTER(pointer)], ctypes.c_int32),
            'SecItemUpdate': ([pointer, pointer], ctypes.c_int32),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.sec, name)
            function.argtypes, function.restype = arguments, result
        signatures = {
            'CFStringCreateWithCString': ([pointer, ctypes.c_char_p, ctypes.c_uint32], pointer),
            'CFDataCreate': ([pointer, ctypes.c_void_p, index], pointer),
            'CFArrayCreate': ([pointer, ctypes.POINTER(pointer), index, pointer], pointer),
            'CFDictionaryCreate': ([pointer, ctypes.POINTER(pointer), ctypes.POINTER(pointer),
                                    index, pointer, pointer], pointer),
            'CFGetTypeID': ([pointer], ctypes.c_ulong),
            'CFDataGetTypeID': ([], ctypes.c_ulong),
            'CFDataGetLength': ([pointer], index),
            'CFDataGetBytePtr': ([pointer], pointer),
            'CFRelease': ([pointer], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.cf, name)
            function.argtypes, function.restype = arguments, result

    def get_interaction_allowed(self) -> bool:
        allowed = ctypes.c_ubyte(255)
        _status(self.sec.SecKeychainGetUserInteractionAllowed(ctypes.byref(allowed)))
        if allowed.value not in (0, 1):
            raise KeychainError('native_failure')
        return bool(allowed.value)

    def set_interaction_allowed(self, allowed: bool) -> None:
        _status(self.sec.SecKeychainSetUserInteractionAllowed(int(allowed)))

    def open_keychain(self, path: str) -> int:
        reference = ctypes.c_void_p()
        status = self.sec.SecKeychainOpen(path.encode('utf-8'), ctypes.byref(reference))
        if status or not reference.value:
            if reference.value:
                self.cf.CFRelease(reference.value)
            _status(status)
            raise KeychainError('keychain_unavailable')
        return reference.value

    def release_keychain(self, reference: int) -> None:
        self.cf.CFRelease(reference)

    @contextmanager
    def _references(self):
        owned = []
        def take(value):
            if not value:
                raise KeychainError('native_failure')
            owned.append(value)
            return value
        try:
            yield take
        finally:
            for reference in reversed(owned):
                self.cf.CFRelease(reference)

    def _dictionary(self, values: dict[str, int], take) -> int:
        keys = (ctypes.c_void_p * len(values))(*(self.symbols[key] for key in values))
        refs = (ctypes.c_void_p * len(values))(*values.values())
        return take(self.cf.CFDictionaryCreate(None, keys, refs, len(values),
                                               self.key_callbacks, self.value_callbacks))

    def _attributes(self, service: str, account: str, take) -> dict[str, int]:
        return {
            'kSecClass': self.symbols['kSecClassGenericPassword'],
            'kSecAttrService': take(self.cf.CFStringCreateWithCString(None, service.encode('utf-8'), 0x08000100)),
            'kSecAttrAccount': take(self.cf.CFStringCreateWithCString(None, account.encode('utf-8'), 0x08000100)),
        }

    def _query(self, reference: int, service: str, account: str, take, *, read=False) -> int:
        values = self._attributes(service, account, take)
        refs = (ctypes.c_void_p * 1)(reference)
        values['kSecMatchSearchList'] = take(self.cf.CFArrayCreate(None, refs, 1, self.array_callbacks))
        if read:
            values['kSecReturnData'] = self.true
            values['kSecMatchLimit'] = self.symbols['kSecMatchLimitOne']
        return self._dictionary(values, take)

    def _data(self, payload: bytes, take) -> int:
        buffer = ctypes.create_string_buffer(payload)
        return take(self.cf.CFDataCreate(None, buffer, len(payload)))

    def read(self, reference: int, service: str, account: str) -> bytes:
        result = ctypes.c_void_p()
        with self._references() as take:
            query = self._query(reference, service, account, take, read=True)
            try:
                _status(self.sec.SecItemCopyMatching(query, ctypes.byref(result)))
                if not result.value or self.cf.CFGetTypeID(result.value) != self.cf.CFDataGetTypeID():
                    raise KeychainError('invalid_payload')
                length = self.cf.CFDataGetLength(result.value)
                if not 0 < length <= MAX_PAYLOAD_BYTES:
                    raise KeychainError('invalid_payload')
                data = self.cf.CFDataGetBytePtr(result.value)
                if not data:
                    raise KeychainError('invalid_payload')
                return ctypes.string_at(data, length)
            finally:
                if result.value:
                    self.cf.CFRelease(result.value)

    def create(self, reference: int, service: str, account: str, payload: bytes) -> None:
        with self._references() as take:
            values = self._attributes(service, account, take)
            values['kSecUseKeychain'] = reference
            values['kSecValueData'] = self._data(payload, take)
            attributes = self._dictionary(values, take)
            _status(self.sec.SecItemAdd(attributes, None))

    def update(self, reference: int, service: str, account: str, payload: bytes) -> None:
        with self._references() as take:
            query = self._query(reference, service, account, take)
            attributes = self._dictionary({'kSecValueData': self._data(payload, take)}, take)
            _status(self.sec.SecItemUpdate(query, attributes))
