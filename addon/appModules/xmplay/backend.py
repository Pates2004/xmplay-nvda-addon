"""Low-level, skin-independent communication with XMPlay.

XMPlay exposes a useful subset of the classic Winamp IPC interface and its
own documented DDE command interface.  Keeping that code in this module makes
it possible to test it without importing NVDA.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import mmap
import os
from pathlib import Path
import struct
from typing import Callable, Iterable


WM_USER = 0x0400
WM_XMPLAY_COMMAND = 0x041A
SMTO_ABORTIFHUNG = 0x0002
GA_ROOT = 2
GUI_MENU_FLAGS = 0x04 | 0x08 | 0x10
PLAYER_WINDOW_CLASSES = frozenset(("XMPLAY-MAIN", "XMPLAY-PANEL"))

# Classic Winamp IPC messages implemented by XMPlay.
IPC_STARTPLAY = 102
IPC_ISPLAYING = 104
IPC_GETOUTPUTTIME = 105
IPC_SETPLAYLISTPOS = 121
IPC_SETVOLUME = 122
IPC_SETPANNING = 123
IPC_GETLISTLENGTH = 124
IPC_GETLISTPOS = 125
IPC_GETINFO = 126
IPC_GETPLAYLISTFILE = 211
IPC_GETPLAYLISTTITLE = 212

# DDEML constants.
APPCMD_CLIENTONLY = 0x0010
CP_WINUNICODE = 1200
CF_TEXT = 1
XTYP_EXECUTE = 0x4050
XTYP_REQUEST = 0x20B0
QID_SYNC = 0xFFFFFFFF

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

PLAYBACK_STOPPED = 0
PLAYBACK_PLAYING = 1
PLAYBACK_PAUSED = 3


def N_(message: str) -> str:
	"""Mark a backend message for translation at the user-interface boundary."""
	return message


class XMPlayError(RuntimeError):
	"""Raised when XMPlay cannot complete a requested operation."""

	def __init__(self, message: str, **parameters):
		self.message = message
		self.parameters = parameters
		super().__init__(message.format(**parameters))


class _GUITHREADINFO(ctypes.Structure):
	_fields_ = (
		("cbSize", wintypes.DWORD),
		("flags", wintypes.DWORD),
		("hwndActive", wintypes.HWND),
		("hwndFocus", wintypes.HWND),
		("hwndCapture", wintypes.HWND),
		("hwndMenuOwner", wintypes.HWND),
		("hwndMoveSize", wintypes.HWND),
		("hwndCaret", wintypes.HWND),
		("rcCaret", wintypes.RECT),
	)


class _SecurityQualityOfService(ctypes.Structure):
	_fields_ = (
		("Length", wintypes.DWORD),
		("ImpersonationLevel", ctypes.c_int),
		("ContextTrackingMode", ctypes.c_ubyte),
		("EffectiveOnly", ctypes.c_ubyte),
	)


class _ConvContext(ctypes.Structure):
	_fields_ = (
		("cb", wintypes.UINT), ("wFlags", wintypes.UINT), ("wCountryID", wintypes.UINT),
		("iCodePage", ctypes.c_int), ("dwLangID", wintypes.DWORD), ("dwSecurity", wintypes.DWORD),
		("qos", _SecurityQualityOfService),
	)


class _ConvInfo(ctypes.Structure):
	_fields_ = (
		("cb", wintypes.DWORD), ("hUser", ctypes.c_size_t), ("hConvPartner", ctypes.c_void_p),
		("hszSvcPartner", ctypes.c_void_p), ("hszServiceReq", ctypes.c_void_p),
		("hszTopic", ctypes.c_void_p), ("hszItem", ctypes.c_void_p),
		("wFmt", wintypes.UINT), ("wType", wintypes.UINT), ("wStatus", wintypes.UINT),
		("wConvst", wintypes.UINT), ("wLastError", wintypes.UINT),
		("hConvList", ctypes.c_void_p), ("ConvCtxt", _ConvContext),
		("hwnd", wintypes.HWND), ("hwndPartner", wintypes.HWND),
	)


@dataclass(frozen=True)
class Track:
	index: int
	title: str
	path: str


@dataclass(frozen=True)
class Status:
	state: int
	title: str
	position_ms: int
	length_seconds: int
	volume_percent: int
	balance_percent: int
	playlist_position: int
	playlist_length: int
	sample_rate_khz: int
	bitrate_kbps: int
	channels: int


@dataclass(frozen=True)
class ShortcutBinding:
	"""One keyboard shortcut record stored by XMPlay in xmplay.ini."""

	command: int
	vk_code: int
	modifier_flags: int
	scan_code: int
	is_extended: bool


def parse_shortcuts(value: str) -> list[ShortcutBinding]:
	"""Decode XMPlay's eight-byte shortcut records from its hexadecimal INI value."""
	try:
		raw = bytes.fromhex(value.strip())
	except ValueError as error:
		raise ValueError("XMPlay shortcut data is not valid hexadecimal") from error
	if len(raw) % 8:
		raise ValueError("XMPlay shortcut data has an incomplete record")
	bindings = []
	for offset in range(0, len(raw), 8):
		command, vk_code, modifier_flags, scan_code, key_flags = struct.unpack_from(
			"<IBBBB",
			raw,
			offset,
		)
		if vk_code:
			bindings.append(
				ShortcutBinding(
					command=command,
					vk_code=vk_code,
					modifier_flags=modifier_flags,
					scan_code=scan_code,
					is_extended=bool(key_flags & 1),
				)
			)
	return bindings


def load_shortcuts(path: str | os.PathLike[str]) -> list[ShortcutBinding]:
	"""Load the current shortcut map without using ConfigParser's value rewriting."""
	for line in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
		key, separator, value = line.partition("=")
		if separator and key.strip().casefold() == "shortcuts":
			return parse_shortcuts(value)
	return []


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_DDECALLBACK = ctypes.WINFUNCTYPE(
	ctypes.c_void_p,
	ctypes.c_uint,
	ctypes.c_uint,
	ctypes.c_void_p,
	ctypes.c_void_p,
	ctypes.c_void_p,
	ctypes.c_void_p,
	ctypes.c_size_t,
	ctypes.c_size_t,
)

_user32.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
_user32.EnumWindows.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.IsWindow.argtypes = (wintypes.HWND,)
_user32.IsWindow.restype = wintypes.BOOL
_user32.GetForegroundWindow.argtypes = ()
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_user32.GetAncestor.restype = wintypes.HWND
_user32.IsWindowEnabled.argtypes = (wintypes.HWND,)
_user32.IsWindowEnabled.restype = wintypes.BOOL
_user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(_GUITHREADINFO))
_user32.GetGUIThreadInfo.restype = wintypes.BOOL
_user32.SendMessageTimeoutW.argtypes = (
	wintypes.HWND,
	wintypes.UINT,
	ctypes.c_size_t,
	ctypes.c_ssize_t,
	wintypes.UINT,
	wintypes.UINT,
	ctypes.POINTER(ctypes.c_size_t),
)
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM

_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.ReadProcessMemory.argtypes = (
	wintypes.HANDLE,
	ctypes.c_void_p,
	ctypes.c_void_p,
	ctypes.c_size_t,
	ctypes.POINTER(ctypes.c_size_t),
)
_kernel32.ReadProcessMemory.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL

_user32.DdeInitializeW.argtypes = (
	ctypes.POINTER(wintypes.DWORD),
	_DDECALLBACK,
	wintypes.DWORD,
	wintypes.DWORD,
)
_user32.DdeInitializeW.restype = wintypes.UINT
_user32.DdeCreateStringHandleW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, ctypes.c_int)
_user32.DdeCreateStringHandleW.restype = ctypes.c_void_p
_user32.DdeConnectList.argtypes = (wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_user32.DdeConnectList.restype = ctypes.c_void_p
_user32.DdeQueryNextServer.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
_user32.DdeQueryNextServer.restype = ctypes.c_void_p
_user32.DdeQueryConvInfo.argtypes = (ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_ConvInfo))
_user32.DdeQueryConvInfo.restype = wintypes.UINT
_user32.DdeClientTransaction.argtypes = (
	ctypes.c_void_p,
	wintypes.DWORD,
	ctypes.c_void_p,
	ctypes.c_void_p,
	wintypes.UINT,
	wintypes.UINT,
	wintypes.DWORD,
	ctypes.POINTER(wintypes.DWORD),
)
_user32.DdeClientTransaction.restype = ctypes.c_void_p
_user32.DdeAccessData.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD))
_user32.DdeAccessData.restype = ctypes.c_void_p
_user32.DdeUnaccessData.argtypes = (ctypes.c_void_p,)
_user32.DdeUnaccessData.restype = wintypes.BOOL
_user32.DdeFreeDataHandle.argtypes = (ctypes.c_void_p,)
_user32.DdeFreeDataHandle.restype = wintypes.BOOL
_user32.DdeDisconnectList.argtypes = (ctypes.c_void_p,)
_user32.DdeDisconnectList.restype = wintypes.BOOL
_user32.DdeFreeStringHandle.argtypes = (wintypes.DWORD, ctypes.c_void_p)
_user32.DdeFreeStringHandle.restype = wintypes.BOOL
_user32.DdeUninitialize.argtypes = (wintypes.DWORD,)
_user32.DdeUninitialize.restype = wintypes.BOOL
_user32.DdeGetLastError.argtypes = (wintypes.DWORD,)
_user32.DdeGetLastError.restype = wintypes.UINT


def _signed32(value: int) -> int:
	value &= 0xFFFFFFFF
	return value - 0x100000000 if value & 0x80000000 else value


def _decode_xmplay(raw: bytes) -> str:
	"""Decode XMPlay's UTF-8 strings, with a legacy system-codepage fallback."""
	raw = raw.split(b"\0", 1)[0]
	if not raw:
		return ""
	try:
		return raw.decode("utf-8")
	except UnicodeDecodeError:
		return raw.decode("mbcs", errors="replace")


def _dde_callback(*_args):
	return None


class _DDEConversation:
	"""A short-lived DDE client conversation."""

	def __init__(self, topic: str, process_id: int):
		self._instance = wintypes.DWORD(0)
		self._callback = _DDECALLBACK(_dde_callback)
		self._service = None
		self._topic = None
		self._conversation = None
		self._conversation_list = None
		result = _user32.DdeInitializeW(
			ctypes.byref(self._instance),
			self._callback,
			APPCMD_CLIENTONLY,
			0,
		)
		if result:
			raise XMPlayError(N_("DDE initialization failed ({code})"), code=result)
		try:
			self._service = self._make_string("XMPlay")
			self._topic = self._make_string(topic)
			self._conversation_list = _user32.DdeConnectList(
				self._instance.value,
				self._service,
				self._topic,
				None,
				None,
			)
			if not self._conversation_list:
				raise self._error(N_("Cannot connect to XMPlay (DDE error {code})"))
			conversation = None
			while conversation := _user32.DdeQueryNextServer(self._conversation_list, conversation):
				info = _ConvInfo(cb=ctypes.sizeof(_ConvInfo))
				if not _user32.DdeQueryConvInfo(conversation, QID_SYNC, ctypes.byref(info)):
					continue
				pid = wintypes.DWORD()
				_user32.GetWindowThreadProcessId(info.hwndPartner, ctypes.byref(pid))
				if pid.value == process_id:
					self._conversation = conversation
					break
			if not self._conversation:
				raise XMPlayError(N_("Cannot connect to the selected XMPlay process ({process})"), process=process_id)
		except Exception:
			self.close()
			raise

	def _make_string(self, value: str):
		handle = _user32.DdeCreateStringHandleW(
			self._instance.value,
			value,
			CP_WINUNICODE,
		)
		if not handle:
			raise self._error(N_("Cannot create a DDE string (DDE error {code})"))
		return handle

	def _error(self, message: str, **parameters) -> XMPlayError:
		code = _user32.DdeGetLastError(self._instance.value) if self._instance.value else 0
		return XMPlayError(message, code=code, **parameters)

	def execute(self, command: str, timeout_ms: int = 3000) -> None:
		data = command.encode("utf-16-le") + b"\0\0"
		buffer = ctypes.create_string_buffer(data)
		transaction_result = wintypes.DWORD(0)
		result = _user32.DdeClientTransaction(
			ctypes.cast(buffer, ctypes.c_void_p),
			len(data),
			self._conversation,
			None,
			0,
			XTYP_EXECUTE,
			timeout_ms,
			ctypes.byref(transaction_result),
		)
		if not result:
			raise self._error(
				N_("XMPlay rejected command {command!r} (DDE error {code})"), command=command,
			)

	def request(self, item: str, timeout_ms: int = 3000) -> str:
		item_handle = self._make_string(item)
		data_handle = None
		try:
			transaction_result = wintypes.DWORD(0)
			data_handle = _user32.DdeClientTransaction(
				None,
				0,
				self._conversation,
				item_handle,
				CF_TEXT,
				XTYP_REQUEST,
				timeout_ms,
				ctypes.byref(transaction_result),
			)
			if not data_handle:
				raise self._error(N_("XMPlay did not return {item} (DDE error {code})"), item=item)
			size = wintypes.DWORD(0)
			pointer = _user32.DdeAccessData(data_handle, ctypes.byref(size))
			if not pointer:
				raise self._error(N_("Cannot access XMPlay data for {item} (DDE error {code})"), item=item)
			try:
				raw = ctypes.string_at(pointer, size.value)
			finally:
				_user32.DdeUnaccessData(data_handle)
			return _decode_xmplay(raw)
		finally:
			if data_handle:
				_user32.DdeFreeDataHandle(data_handle)
			if item_handle:
				_user32.DdeFreeStringHandle(self._instance.value, item_handle)

	def close(self) -> None:
		if self._conversation_list:
			_user32.DdeDisconnectList(self._conversation_list)
			self._conversation_list = None
		self._conversation = None
		if self._service and self._instance.value:
			_user32.DdeFreeStringHandle(self._instance.value, self._service)
			self._service = None
		if self._topic and self._instance.value:
			_user32.DdeFreeStringHandle(self._instance.value, self._topic)
			self._topic = None
		if self._instance.value:
			_user32.DdeUninitialize(self._instance.value)
			self._instance.value = 0

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.close()


class XMPlayController:
	"""Query and control a particular XMPlay process."""

	def __init__(self, process_id: int):
		self.process_id = int(process_id)
		self._hwnd = 0

	def _find_window(self) -> int:
		matches: list[int] = []

		@_WNDENUMPROC
		def callback(hwnd, _l_param):
			pid = wintypes.DWORD(0)
			_user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
			if pid.value != self.process_id:
				return True
			class_name = ctypes.create_unicode_buffer(64)
			_user32.GetClassNameW(hwnd, class_name, len(class_name))
			if class_name.value == "XMPLAY-MAIN":
				matches.append(int(hwnd))
				return False
			return True

		_user32.EnumWindows(callback, 0)
		return matches[0] if matches else 0

	def _get_window(self) -> int:
		if self._hwnd and _user32.IsWindow(self._hwnd):
			pid = wintypes.DWORD(0)
			_user32.GetWindowThreadProcessId(self._hwnd, ctypes.byref(pid))
			if pid.value == self.process_id:
				return self._hwnd
		self._hwnd = self._find_window()
		if not self._hwnd:
			raise XMPlayError(N_("XMPlay's main window was not found"))
		return self._hwnd

	def is_available(self) -> bool:
		try:
			self._get_window()
			return True
		except XMPlayError:
			return False

	def can_handle_native_shortcuts(self) -> bool:
		"""Only replace keys on the skinned player, never in dialogs or menus."""
		foreground = _user32.GetForegroundWindow()
		if not foreground:
			return False
		pid = wintypes.DWORD()
		thread_id = _user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
		if pid.value != self.process_id:
			return False
		info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
		if not _user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
			return False
		if info.flags & GUI_MENU_FLAGS or not info.hwndFocus:
			return False
		for hwnd in (foreground, info.hwndFocus, _user32.GetAncestor(info.hwndFocus, GA_ROOT)):
			name = ctypes.create_unicode_buffer(64)
			if not hwnd or not _user32.IsWindowEnabled(hwnd):
				return False
			_user32.GetClassNameW(hwnd, name, len(name))
			if name.value not in PLAYER_WINDOW_CLASSES:
				return False
		return True

	def _send_ipc(self, parameter: int, command: int) -> int:
		result = ctypes.c_size_t(0)
		pointer_bits = ctypes.sizeof(ctypes.c_size_t) * 8
		w_param = parameter & ((1 << pointer_bits) - 1)
		sent = _user32.SendMessageTimeoutW(
			self._get_window(),
			WM_USER,
			w_param,
			command,
			SMTO_ABORTIFHUNG,
			1000,
			ctypes.byref(result),
		)
		if not sent:
			raise XMPlayError(N_("XMPlay did not answer IPC command {command}"), command=command)
		return int(result.value)

	def _window_title(self) -> str:
		buffer = ctypes.create_unicode_buffer(2048)
		_user32.GetWindowTextW(self._get_window(), buffer, len(buffer))
		return buffer.value.strip()

	def playback_state(self) -> int:
		return _signed32(self._send_ipc(0, IPC_ISPLAYING))

	def playlist_length(self) -> int:
		return max(0, _signed32(self._send_ipc(0, IPC_GETLISTLENGTH)))

	def playlist_position(self) -> int:
		return _signed32(self._send_ipc(0, IPC_GETLISTPOS))

	def _open_process(self):
		handle = _kernel32.OpenProcess(
			PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
			False,
			self.process_id,
		)
		if not handle:
			raise XMPlayError(N_("Cannot read XMPlay process memory ({code})"), code=ctypes.get_last_error())
		return handle

	def _read_remote_string(self, process_handle, address: int) -> str:
		address &= 0xFFFFFFFF
		if address <= 1:
			return ""
		data = bytearray()
		# A valid short string may end just before an inaccessible page. Do not
		# include the following page in a ReadProcessMemory request.
		while len(data) < 65536:
			chunk_size = min(mmap.PAGESIZE - address % mmap.PAGESIZE, 65536 - len(data))
			buffer = ctypes.create_string_buffer(chunk_size)
			bytes_read = ctypes.c_size_t(0)
			ok = _kernel32.ReadProcessMemory(
				process_handle,
				ctypes.c_void_p(address),
				buffer,
				chunk_size,
				ctypes.byref(bytes_read),
			)
			if not ok or not bytes_read.value:
				return ""
			chunk = buffer.raw[: bytes_read.value]
			terminator = chunk.find(b"\0")
			if terminator >= 0:
				data.extend(chunk[:terminator])
				return _decode_xmplay(bytes(data))
			data.extend(chunk)
			address += bytes_read.value
		return ""

	def _track_with_handle(self, index: int, process_handle) -> Track:
		if index < 0 or index >= self.playlist_length():
			raise IndexError(index)
		title_pointer = self._send_ipc(index, IPC_GETPLAYLISTTITLE)
		file_pointer = self._send_ipc(index, IPC_GETPLAYLISTFILE)
		title = self._read_remote_string(process_handle, title_pointer)
		path = self._read_remote_string(process_handle, file_pointer)
		if not title and path:
			title = os.path.basename(path)
		return Track(index=index, title=title, path=path)

	def get_track(self, index: int) -> Track:
		handle = self._open_process()
		try:
			return self._track_with_handle(index, handle)
		finally:
			_kernel32.CloseHandle(handle)

	def get_playlist(
		self, maximum_entries: int = 100000, *, cancelled: Callable[[], bool] | None = None,
	) -> list[Track]:
		if cancelled and cancelled():
			return []
		count = min(self.playlist_length(), maximum_entries)
		if not count:
			return []
		handle = self._open_process()
		try:
			tracks = []
			for index in range(count):
				if cancelled and cancelled():
					return []
				tracks.append(self._track_with_handle(index, handle))
			return tracks
		finally:
			_kernel32.CloseHandle(handle)

	def current_title(self, position: int | None = None) -> str:
		if position is None:
			position = self.playlist_position()
		if 0 <= position < self.playlist_length():
			try:
				return self.get_track(position).title
			except (IndexError, XMPlayError):
				pass
		title = self._window_title()
		return "" if title.casefold() == "xmplay" else title

	def status(self) -> Status:
		state = self.playback_state()
		position = _signed32(self._send_ipc(0, IPC_GETOUTPUTTIME))
		length = _signed32(self._send_ipc(1, IPC_GETOUTPUTTIME))
		volume = _signed32(self._send_ipc(-666, IPC_SETVOLUME))
		balance = _signed32(self._send_ipc(-666, IPC_SETPANNING))
		playlist_position = self.playlist_position()
		playlist_length = self.playlist_length()
		sample_rate = _signed32(self._send_ipc(0, IPC_GETINFO))
		bitrate = _signed32(self._send_ipc(1, IPC_GETINFO))
		channels = _signed32(self._send_ipc(2, IPC_GETINFO))
		if position < 0:
			position = 0
		if length < 0:
			length = 0
		volume_percent = max(0, min(100, round(volume * 100 / 255))) if volume >= 0 else 0
		# XMPlay exposes balance in the older Winamp range: 0 left, 127 center, 255 right.
		balance_scale = 127 if balance < 127 else 128
		balance_percent = max(-100, min(100, round((balance - 127) * 100 / balance_scale)))
		return Status(
			state=state,
			title=self.current_title(playlist_position),
			position_ms=position,
			length_seconds=length,
			volume_percent=volume_percent,
			balance_percent=balance_percent,
			playlist_position=playlist_position,
			playlist_length=playlist_length,
			sample_rate_khz=max(0, sample_rate),
			bitrate_kbps=max(0, bitrate),
			channels=max(0, channels),
		)

	def execute(self, command: str) -> None:
		with _DDEConversation("System", self.process_id) as conversation:
			conversation.execute(command)

	def execute_many(
		self, commands: Iterable[str], *, cancelled: Callable[[], bool] | None = None,
	) -> None:
		if cancelled and cancelled():
			return
		with _DDEConversation("System", self.process_id) as conversation:
			for command in commands:
				if cancelled and cancelled():
					return
				conversation.execute(command)

	def command(self, key_id: int) -> None:
		result = ctypes.c_size_t(0)
		sent = _user32.SendMessageTimeoutW(
			self._get_window(),
			WM_XMPLAY_COMMAND,
			int(key_id),
			0,
			SMTO_ABORTIFHUNG,
			1000,
			ctypes.byref(result),
		)
		if not sent:
			raise XMPlayError(N_("XMPlay did not answer control command {command}"), command=key_id)

	def commands(self, key_ids: Iterable[int]) -> None:
		for key_id in key_ids:
			self.command(key_id)

	def request_info(self, section: int) -> str:
		if section not in (1, 2, 3):
			raise ValueError(section)
		# XMPlay 3.8 uses zero-based DDE topics internally, although the user-facing
		# manual numbers the General, Message, and Samples pages from one to three.
		item = f"info{section - 1}"
		with _DDEConversation(item, self.process_id) as conversation:
			return conversation.request(item)

	def open_paths(
		self, paths: Iterable[str], replace: bool, *, cancelled: Callable[[], bool] | None = None,
	) -> None:
		commands = []
		for path in paths:
			# XMPlay 3.8.4 treats quotes as part of the filename. The complete
			# unquoted argument supports spaces and Unicode through Unicode DDE.
			filename = os.fspath(path)
			commands.append(f"[list({filename})]")
		if commands:
			if replace:
				# Native "open" follows XMPlay integration settings and may merge
				# successive calls into one batch. Clear list entries (not files),
				# then append and play explicitly, inside the PID-bound connection.
				commands = ["key341", "key370", *commands, "key346", "key372"]
			self.execute_many(commands, cancelled=cancelled)

	def play_track(self, index: int, *, cancelled: Callable[[], bool] | None = None) -> None:
		"""Select an exact playlist entry through XMPlay's documented list commands."""
		if cancelled and cancelled():
			return
		count = self.playlist_length()
		if index < 0 or index >= count:
			raise IndexError(index)
		current = self.playlist_position()
		if 0 <= current < count:
			commands = ["key340"]  # Jump selection to the current track.
			difference = index - current
			move_command = "key337" if difference >= 0 else "key336"
			commands.extend(move_command for _ in range(abs(difference)))
		else:
			commands = ["key346"]  # Top of list.
			commands.extend("key337" for _ in range(index))
		commands.append("key372")  # Play the selected list entry.
		self.execute_many(commands, cancelled=cancelled)
