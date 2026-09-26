"""Synthetic secure-store and fake Security.framework tests; no host Keychain use."""
import ctypes
from dataclasses import FrozenInstanceError
from pathlib import Path
import threading
import time
import traceback

import pytest

from notebooklm_mcp.doc_refresh import google_keychain as keychain


SELECTION = keychain.KeychainSelection(
    Path('/fictional/Library/Keychains/login.keychain-db'),
    'c021.notebooklm.google-data-oauth.v1', 'jeremybradford1977@gmail.com',
)
SECRET = b'fictional-sensitive-refresh-grant'


class FakeBackend:
    def __init__(self):
        self.allowed = True
        self.payload = None
        self.calls = []
        self.failure = None

    def record(self, action, *args):
        self.calls.append((action, *args))
        if self.failure == action:
            raise RuntimeError(SECRET.decode())

    def get_interaction_allowed(self):
        self.record('get_interaction')
        return self.allowed

    def set_interaction_allowed(self, allowed):
        self.record('set_interaction', allowed)
        self.allowed = allowed

    def open_keychain(self, path):
        self.record('open', path)
        return 'exact-keychain-reference'

    def release_keychain(self, reference):
        self.record('release', reference)

    def read(self, reference, service, account):
        self.record('read', reference, service, account)
        if self.payload is None:
            raise keychain.KeychainError('not_found')
        return self.payload

    def create(self, reference, service, account, payload):
        self.record('create', reference, service, account)
        if self.payload is not None:
            raise keychain.KeychainError('already_exists')
        self.payload = payload

    def update(self, reference, service, account, payload):
        self.record('update', reference, service, account)
        self.payload = payload


@pytest.fixture(autouse=True)
def forbid_real_native_library(monkeypatch):
    monkeypatch.setattr(keychain, '_INTERACTION_POISONED', False)
    def forbidden(*_args, **_kwargs):
        pytest.fail('Test attempted to load a real native framework')
    monkeypatch.setattr(ctypes, 'CDLL', forbidden)


def test_exact_selection_create_read_update_and_interaction_restoration():
    backend = FakeBackend()
    store = keychain.KeychainStore(SELECTION, backend=backend)
    store.create(SECRET)
    assert store.read() == SECRET
    store.update(SECRET, b'renewed-fictional-grant')
    assert backend.payload == b'renewed-fictional-grant'
    assert backend.allowed is True
    assert all(call[1:] == (str(SELECTION.path),) for call in backend.calls if call[0] == 'open')
    for call in backend.calls:
        if call[0] in {'read', 'create', 'update'}:
            assert call[1:] == ('exact-keychain-reference', SELECTION.service, SELECTION.account)
    assert [call for call in backend.calls if call[0] == 'set_interaction'] == [
        ('set_interaction', False), ('set_interaction', True),
        ('set_interaction', False), ('set_interaction', True),
        ('set_interaction', False), ('set_interaction', True),
    ]
    assert [call[0] for call in backend.calls[-7:]] == [
        'get_interaction', 'set_interaction', 'open', 'read', 'update', 'release', 'set_interaction',
    ]


def test_create_refuses_existing_and_update_refuses_changed_expected_value():
    backend = FakeBackend()
    backend.payload = SECRET
    store = keychain.KeychainStore(SELECTION, backend=backend)
    with pytest.raises(keychain.KeychainError, match='already_exists'):
        store.create(b'new')
    with pytest.raises(keychain.KeychainError, match='conflict'):
        store.update(b'incorrect-expected', b'new')
    assert backend.payload == SECRET
    assert not any(call[0] == 'update' for call in backend.calls)


def test_interactive_setup_is_explicit_and_previous_disabled_setting_is_restored():
    backend = FakeBackend()
    backend.allowed = False
    store = keychain.KeychainStore(SELECTION, backend=backend)
    store.create(SECRET, interactive=True)
    assert backend.allowed is False
    assert ('set_interaction', True) in backend.calls
    assert backend.calls[-1] == ('set_interaction', False)


@pytest.mark.parametrize('method', ['read', 'create', 'update'])
@pytest.mark.parametrize('value', [1, None, 'true'])
def test_interaction_flag_is_an_explicit_boolean(method, value):
    backend = FakeBackend()
    store = keychain.KeychainStore(SELECTION, backend=backend)
    args = {'read': (), 'create': (SECRET,), 'update': (SECRET, b'new')}[method]
    with pytest.raises(keychain.KeychainError, match='invalid_configuration'):
        getattr(store, method)(*args, interactive=value)
    assert backend.calls == []


@pytest.mark.parametrize('value', [b'', b'x' * 65537, bytearray(b'bad'), 'bad', None])
def test_payload_limits_are_checked_before_native_access(value):
    backend = FakeBackend()
    store = keychain.KeychainStore(SELECTION, backend=backend)
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.create(value)
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.update(value, SECRET)
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.update(SECRET, value)
    assert backend.calls == []


def test_maximum_payload_is_supported_and_bad_stored_payload_is_refused():
    backend = FakeBackend()
    store = keychain.KeychainStore(SELECTION, backend=backend)
    store.create(b'x' * 65536)
    assert len(store.read()) == 65536
    backend.payload = b'x' * 65537
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.read()
    assert backend.allowed is True


@pytest.mark.parametrize('failure', ['get_interaction', 'open', 'read', 'release'])
def test_backend_failures_are_redacted_without_sensitive_exception_chain(failure):
    backend = FakeBackend()
    backend.payload = SECRET
    backend.failure = failure
    store = keychain.KeychainStore(SELECTION, backend=backend)
    with pytest.raises(keychain.KeychainError) as caught:
        store.read()
    assert SECRET.decode() not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert SECRET.decode() not in ''.join(traceback.format_exception(caught.value))
    assert backend.allowed is True


def test_failed_disable_attempt_still_restores_known_previous_setting():
    class Backend(FakeBackend):
        def set_interaction_allowed(self, allowed):
            self.calls.append(('set_interaction', allowed))
            self.allowed = allowed
            if allowed is False:
                raise RuntimeError(SECRET.decode())
    backend = Backend()
    with pytest.raises(keychain.KeychainError):
        keychain.KeychainStore(SELECTION, backend=backend).read()
    assert backend.allowed is True
    assert [call[0] for call in backend.calls] == ['get_interaction', 'set_interaction', 'set_interaction']


def test_failed_restoration_poison_stops_later_store_access_in_process():
    class Backend(FakeBackend):
        def set_interaction_allowed(self, allowed):
            self.calls.append(('set_interaction', allowed))
            if allowed:
                raise RuntimeError(SECRET.decode())
            self.allowed = allowed
    backend = Backend()
    backend.payload = SECRET
    with pytest.raises(keychain.KeychainError, match='interaction_restore_failed'):
        keychain.KeychainStore(SELECTION, backend=backend).read()
    other = FakeBackend()
    with pytest.raises(keychain.KeychainError, match='interaction_restore_failed'):
        keychain.KeychainStore(SELECTION, backend=other).read()
    assert other.calls == []


def test_operations_from_different_stores_serialize_global_interaction_state():
    entered, release = threading.Event(), threading.Event()
    class WaitingBackend(FakeBackend):
        def read(self, *args):
            entered.set()
            assert release.wait(2)
            return super().read(*args)
    first, second = WaitingBackend(), FakeBackend()
    first.payload = second.payload = SECRET
    results, errors = [], []
    def run(backend):
        try:
            results.append(keychain.KeychainStore(SELECTION, backend=backend).read())
        except BaseException as exc:
            errors.append(exc)
    one = threading.Thread(target=run, args=(first,))
    two = threading.Thread(target=run, args=(second,))
    one.start()
    assert entered.wait(1)
    two.start()
    time.sleep(0.02)
    assert not second.calls
    release.set()
    one.join(2)
    two.join(2)
    assert results == [SECRET, SECRET] and not errors
    assert first.allowed is second.allowed is True


@pytest.mark.parametrize('path', [Path('login.keychain-db'), Path('/x/../login.keychain-db'),
                                 Path('/x/other.keychain-db'), Path('/x/login.keychain-db\x00')])
def test_selection_rejects_discovery_or_non_login_paths(path):
    with pytest.raises(keychain.KeychainError, match='invalid_configuration'):
        keychain.KeychainSelection(path, SELECTION.service, SELECTION.account)


@pytest.mark.parametrize('service,account', [
    ('other', SELECTION.account), (SELECTION.service, 'another@example.invalid'),
    (SELECTION.service, SELECTION.account + '\n'),
])
def test_service_and_account_are_pinned(service, account):
    with pytest.raises(keychain.KeychainError, match='invalid_configuration'):
        keychain.KeychainSelection(SELECTION.path, service, account)


def test_selection_is_immutable_and_constructor_does_no_io():
    with pytest.raises(FrozenInstanceError):
        SELECTION.account = 'other'
    keychain.KeychainStore(SELECTION, backend=FakeBackend())


def test_native_backend_is_unavailable_on_other_platforms(monkeypatch):
    monkeypatch.setattr(keychain.sys, 'platform', 'linux')
    with pytest.raises(keychain.KeychainError, match='unsupported_platform'):
        keychain.KeychainStore(SELECTION)


class NativeFunction:
    """Accept ctypes signature declarations while forwarding to a fictional C ABI."""
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


class FakeFramework:
    """CF references and Security calls are Python records, never native objects."""
    def __init__(self):
        self.next_id = 100
        self.objects = {}
        self.constants = {}
        self.allocations = []
        self.released = []
        self.calls = []
        self.items = {}
        self.allowed = True
        self.failures = {}
        self.result_kind = 'data'
        self.length_override = None
        self.null_data_pointer = False
        self.buffers = []
        for name in ['SecKeychainOpen', 'SecKeychainGetUserInteractionAllowed',
                     'SecKeychainSetUserInteractionAllowed', 'SecItemCopyMatching',
                     'SecItemAdd', 'SecItemUpdate', 'CFStringCreateWithCString',
                     'CFDataCreate', 'CFArrayCreate', 'CFDictionaryCreate',
                     'CFGetTypeID', 'CFDataGetTypeID', 'CFDataGetLength',
                     'CFDataGetBytePtr', 'CFRelease']:
            setattr(self, name, NativeFunction(lambda *args, name=name: self.dispatch(name, *args)))

    def allocate(self, kind, value, *, owned=True):
        self.next_id += 1
        self.objects[self.next_id] = (kind, value)
        if owned:
            self.allocations.append(self.next_id)
        return self.next_id

    def constant(self, name):
        if name not in self.constants:
            self.constants[name] = self.allocate('constant', True if name == 'kCFBooleanTrue' else name, owned=False)
        return self.constants[name]

    def value(self, reference):
        return self.objects[reference][1]

    def item_key(self, query, *, adding=False):
        reference = query['kSecUseKeychain'] if adding else query['kSecMatchSearchList'][0]
        return (self.value(reference), query['kSecAttrService'], query['kSecAttrAccount'])

    def dispatch(self, name, *args):
        self.calls.append(name)
        if name in self.failures:
            return self.failures[name]
        if name == 'SecKeychainGetUserInteractionAllowed':
            ctypes.cast(args[0], ctypes.POINTER(ctypes.c_ubyte))[0] = self.allowed
            return 0
        if name == 'SecKeychainSetUserInteractionAllowed':
            self.allowed = bool(args[0])
            return 0
        if name == 'SecKeychainOpen':
            reference = self.allocate('keychain', args[0].decode('utf-8'))
            ctypes.cast(args[1], ctypes.POINTER(ctypes.c_void_p))[0] = reference
            return 0
        if name == 'CFStringCreateWithCString':
            assert args[2] == 0x08000100
            return self.allocate('string', args[1].decode('utf-8'))
        if name == 'CFDataCreate':
            return self.allocate('data', ctypes.string_at(args[1], args[2]))
        if name == 'CFArrayCreate':
            assert args[3] == 777
            return self.allocate('array', [args[1][i] for i in range(args[2])])
        if name == 'CFDictionaryCreate':
            assert args[4:] == (777, 777)
            return self.allocate('dictionary', {self.value(args[1][i]): self.value(args[2][i])
                                                if self.objects[args[2][i]][0] != 'keychain' else args[2][i]
                                                for i in range(args[3])})
        if name == 'CFRelease':
            assert args[0] not in self.released
            assert args[0] in self.allocations
            self.released.append(args[0])
            return None
        if name == 'CFGetTypeID':
            return 50 if self.objects[args[0]][0] == 'data' else 51
        if name == 'CFDataGetTypeID':
            return 50
        if name == 'CFDataGetLength':
            return self.length_override if self.length_override is not None else len(self.value(args[0]))
        if name == 'CFDataGetBytePtr':
            if self.null_data_pointer:
                return None
            buffer = ctypes.create_string_buffer(self.value(args[0]))
            self.buffers.append(buffer)
            return ctypes.addressof(buffer)
        query = self.value(args[0])
        assert query['kSecClass'] == 'kSecClassGenericPassword'
        assert query['kSecAttrService'] == SELECTION.service
        assert query['kSecAttrAccount'] == SELECTION.account
        if name == 'SecItemAdd':
            assert set(query) == {'kSecClass', 'kSecAttrService', 'kSecAttrAccount',
                                  'kSecUseKeychain', 'kSecValueData'}
            assert args[1] is None
            item = self.item_key(query, adding=True)
            if item in self.items:
                return -25299
            self.items[item] = query['kSecValueData']
            return 0
        assert len(query['kSecMatchSearchList']) == 1
        item = self.item_key(query)
        if item not in self.items:
            return -25300
        if name == 'SecItemCopyMatching':
            assert set(query) == {'kSecClass', 'kSecAttrService', 'kSecAttrAccount',
                                  'kSecMatchSearchList', 'kSecReturnData', 'kSecMatchLimit'}
            assert query['kSecReturnData'] is True
            assert query['kSecMatchLimit'] == 'kSecMatchLimitOne'
            reference = self.allocate(self.result_kind, self.items[item])
            ctypes.cast(args[1], ctypes.POINTER(ctypes.c_void_p))[0] = reference
            return 0
        if name == 'SecItemUpdate':
            assert set(query) == {'kSecClass', 'kSecAttrService', 'kSecAttrAccount', 'kSecMatchSearchList'}
            replacement = self.value(args[1])
            assert set(replacement) == {'kSecValueData'}
            self.items[item] = replacement['kSecValueData']
            return 0
        pytest.fail('Unexpected native function')


@pytest.fixture
def fake_native(monkeypatch):
    monkeypatch.setattr(keychain.sys, 'platform', 'darwin')
    framework = FakeFramework()
    monkeypatch.setattr(keychain, '_constant', lambda _library, name: framework.constant(name))
    monkeypatch.setattr(keychain, '_callbacks', lambda _library, _name: 777)
    backend = keychain._SecurityBackend(_security=framework, _core=framework)
    return framework, keychain.KeychainStore(SELECTION, backend=backend)


def test_fake_native_exact_query_add_update_and_cf_releases(fake_native):
    native, store = fake_native
    store.create(SECRET)
    assert store.read() == SECRET
    store.update(SECRET, b'new\x00binary-safe-grant')
    assert store.read() == b'new\x00binary-safe-grant'
    assert native.items == {(str(SELECTION.path), SELECTION.service, SELECTION.account): b'new\x00binary-safe-grant'}
    assert native.allowed is True
    assert native.calls.count('SecItemAdd') == 1
    assert native.calls.count('SecItemUpdate') == 1
    assert native.calls.count('SecItemCopyMatching') == 3
    assert set(native.allocations) == set(native.released)
    assert native.SecKeychainOpen.restype is ctypes.c_int32
    assert native.SecKeychainGetUserInteractionAllowed.argtypes == [ctypes.POINTER(ctypes.c_ubyte)]


def test_fake_native_duplicate_add_does_not_replace_or_delete(fake_native):
    native, store = fake_native
    store.create(SECRET)
    with pytest.raises(keychain.KeychainError, match='already_exists'):
        store.create(b'unapproved-overwrite')
    assert store.read() == SECRET
    assert 'SecItemUpdate' not in native.calls
    assert set(native.allocations) == set(native.released)


@pytest.mark.parametrize('status,code', [
    (-25300, 'not_found'), (-25308, 'interaction_required'), (-25315, 'interaction_required'),
    (-25293, 'access_denied'), (-128, 'access_denied'), (-25292, 'access_denied'),
    (-25291, 'keychain_unavailable'), (-25294, 'keychain_unavailable'),
    (-25295, 'keychain_unavailable'), (-50, 'native_failure'),
])
def test_fake_native_failure_codes_are_redacted_and_restore_ui(fake_native, status, code):
    native, store = fake_native
    native.failures['SecItemCopyMatching'] = status
    with pytest.raises(keychain.KeychainError) as caught:
        store.read()
    assert caught.value.code == code
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert native.allowed is True
    assert set(native.allocations) == set(native.released)


@pytest.mark.parametrize('length', [-1, 0, 65537])
def test_fake_native_length_checked_before_copying_memory(fake_native, length):
    native, store = fake_native
    store.create(SECRET)
    native.length_override = length
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.read()
    assert 'CFDataGetBytePtr' not in native.calls
    assert set(native.allocations) == set(native.released)


def test_fake_native_nondata_result_and_null_pointer_are_refused(fake_native):
    native, store = fake_native
    store.create(SECRET)
    native.result_kind = 'string'
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.read()
    assert 'CFDataGetLength' not in native.calls
    native.result_kind = 'data'
    native.null_data_pointer = True
    with pytest.raises(keychain.KeychainError, match='invalid_payload'):
        store.read()
    assert set(native.allocations) == set(native.released)


def test_fake_native_failed_open_does_not_use_search_list_or_default_store(fake_native):
    native, store = fake_native
    native.failures['SecKeychainOpen'] = -25294
    with pytest.raises(keychain.KeychainError, match='keychain_unavailable'):
        store.read()
    assert 'SecItemCopyMatching' not in native.calls
    assert native.allowed is True


def test_expected_bytes_mismatch_never_reaches_native_update(fake_native):
    native, store = fake_native
    store.create(SECRET)
    with pytest.raises(keychain.KeychainError, match='conflict'):
        store.update(b'outdated-grant', b'new-grant')
    assert 'SecItemUpdate' not in native.calls
    assert set(native.allocations) == set(native.released)
