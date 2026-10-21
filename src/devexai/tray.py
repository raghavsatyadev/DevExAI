"""The DevExAI icon in the Windows notification area (the tray), for the windowed build devexaiw.exe.

A Win32 icon through ctypes, so no extra package: a hidden top-level window on its own thread
receives the icon's clicks. Left click (or a click on a notification) runs `on_open`; right click
shows the menu. A top-level window rather than a message-only one, because only top-level windows
hear TaskbarCreated, which re-adds the icon after Explorer restarts. Off Windows, create() is None.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from collections.abc import Callable
from ctypes import wintypes as w
from pathlib import Path

log = logging.getLogger(__name__)

CLASS = "devexai.tray"
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

WM_NULL, WM_DESTROY, WM_CLOSE, WM_CONTEXTMENU, WM_USER, WM_APP = 0, 0x2, 0x10, 0x7B, 0x400, 0x8000
CALLBACK, OPEN_REQUEST = WM_APP + 1, WM_APP + 2  # icon events; "open the dashboard" from a 2nd launch
STOP_REQUEST = WM_APP + 3  # "quit": the setup sends it before replacing or removing the program
NIN_SELECT, NIN_KEYSELECT, NIN_BALLOONUSERCLICK = WM_USER, WM_USER + 1, WM_USER + 5
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETVERSION = 0, 1, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO, NIF_SHOWTIP = 0x1, 0x2, 0x4, 0x10, 0x80
NIIF_INFO, NIIF_WARNING = 0x1, 0x2
MF_STRING, MF_SEPARATOR = 0x0, 0x800
TPM_RIGHTBUTTON, TPM_BOTTOMALIGN, TPM_RETURNCMD = 0x2, 0x20, 0x100
IMAGE_ICON, LR_LOADFROMFILE, SM_CXSMICON = 1, 0x10, 49
IDI_APPLICATION, MB_ICONERROR = 32512, 0x10


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT),
                ("uCallbackMessage", w.UINT), ("hIcon", w.HICON), ("szTip", w.WCHAR * 128),
                ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256),
                ("uVersion", w.UINT), ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", w.HICON)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
                ("lpszClassName", w.LPCWSTR)]


def _api():
    """user32/shell32 with argument types set: the default c_int would cut 64-bit handles in half."""
    u, s, k = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("shell32"), ctypes.WinDLL("kernel32")
    sigs = {
        (u, "DefWindowProcW"): (LRESULT, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]),
        (u, "RegisterClassW"): (w.ATOM, [ctypes.POINTER(WNDCLASSW)]),
        (u, "CreateWindowExW"): (w.HWND, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]),
        (u, "DestroyWindow"): (w.BOOL, [w.HWND]),
        (u, "PostMessageW"): (w.BOOL, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]),
        (u, "PostQuitMessage"): (None, [ctypes.c_int]),
        (u, "GetMessageW"): (w.BOOL, [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]),
        (u, "TranslateMessage"): (w.BOOL, [ctypes.POINTER(w.MSG)]),
        (u, "DispatchMessageW"): (LRESULT, [ctypes.POINTER(w.MSG)]),
        (u, "RegisterWindowMessageW"): (w.UINT, [w.LPCWSTR]),
        (u, "FindWindowW"): (w.HWND, [w.LPCWSTR, w.LPCWSTR]),
        (u, "CreatePopupMenu"): (w.HMENU, []),
        (u, "AppendMenuW"): (w.BOOL, [w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR]),
        (u, "TrackPopupMenu"): (w.BOOL, [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND,
                                         w.LPVOID]),
        (u, "DestroyMenu"): (w.BOOL, [w.HMENU]),
        (u, "GetCursorPos"): (w.BOOL, [ctypes.POINTER(w.POINT)]),
        (u, "SetForegroundWindow"): (w.BOOL, [w.HWND]),
        (u, "LoadImageW"): (w.HANDLE, [w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT]),
        (u, "LoadIconW"): (w.HICON, [w.HINSTANCE, w.LPVOID]),
        (u, "DestroyIcon"): (w.BOOL, [w.HICON]),
        (u, "GetSystemMetrics"): (ctypes.c_int, [ctypes.c_int]),
        (u, "MessageBoxW"): (ctypes.c_int, [w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT]),
        (s, "Shell_NotifyIconW"): (w.BOOL, [w.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]),
        (k, "GetModuleHandleW"): (w.HMODULE, [w.LPCWSTR]),
    }
    for (dll, name), (res, args) in sigs.items():
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = res, args
    return u, s, k


MenuItem = tuple[str, Callable[[], None]] | None  # None draws a separator


class Tray:
    def __init__(self, tooltip: str, menu: list[MenuItem], on_open: Callable[[], None], icon: Path | None,
                 on_quit: Callable[[], None] | None = None):
        self.tooltip, self.menu, self.on_open, self.icon_path = tooltip, menu, on_open, icon
        self.on_quit = on_quit
        self.user32, self.shell32, self.kernel32 = _api()
        self.hwnd = None
        self._icon = None
        self._ready = threading.Event()
        self._proc = WNDPROC(self._handle)  # kept on self: Windows calls it for as long as the window lives
        self._taskbar_created = self.user32.RegisterWindowMessageW("TaskbarCreated")

    def start(self) -> bool:
        threading.Thread(target=self._run, name="devexai-tray", daemon=True).start()
        self._ready.wait(5)
        return self.hwnd is not None

    def notify(self, title: str, text: str, warning: bool = False) -> None:
        if not self.hwnd:
            return
        data = self._data(NIF_INFO)
        data.szInfoTitle, data.szInfo = title[:63], text[:255]
        data.dwInfoFlags = NIIF_WARNING if warning else NIIF_INFO
        self.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def close(self) -> None:
        hwnd, self.hwnd = self.hwnd, None
        if hwnd:
            data = self._data(0, hwnd)
            self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
            self.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    def _run(self) -> None:
        u = self.user32
        try:
            instance = self.kernel32.GetModuleHandleW(None)
            wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=instance, lpszClassName=CLASS)
            u.RegisterClassW(ctypes.byref(wc))
            hwnd = u.CreateWindowExW(0, CLASS, self.tooltip, 0, 0, 0, 0, 0, None, None, instance, None)
            if not hwnd:
                raise OSError(f"CreateWindowExW failed ({ctypes.get_last_error()})")
            self._icon = self._load_icon()
            self.hwnd = hwnd
            self._add()
        except Exception:
            log.exception("tray icon not created")
        finally:
            self._ready.set()
        msg = w.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))

    def _add(self) -> None:
        data = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP)
        data.uCallbackMessage, data.hIcon, data.szTip = CALLBACK, self._icon, self.tooltip[:127]
        if not self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            log.warning("tray icon not added")
        data.uVersion = 4  # NOTIFYICON_VERSION_4: clicks arrive as NIN_SELECT / WM_CONTEXTMENU
        self.shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(data))

    def _handle(self, hwnd, message, wparam, lparam) -> int:
        try:
            if message == CALLBACK:
                event = lparam & 0xFFFF
                if event in (NIN_SELECT, NIN_KEYSELECT, NIN_BALLOONUSERCLICK):
                    self._safe("open", self.on_open)
                elif event == WM_CONTEXTMENU:
                    self._show_menu(hwnd)
                return 0
            if message == OPEN_REQUEST:
                self._safe("open", self.on_open)
                return 0
            if message == STOP_REQUEST and self.on_quit:
                self._safe("quit", self.on_quit)
                return 0
            if message == self._taskbar_created and self.hwnd:
                self._add()
                return 0
            if message == WM_CLOSE:
                self.user32.DestroyWindow(hwnd)
                return 0
            if message == WM_DESTROY:
                if self._icon:
                    self.user32.DestroyIcon(self._icon)
                self.user32.PostQuitMessage(0)
                return 0
        except Exception:
            log.exception("tray message %s failed", message)
        return self.user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _show_menu(self, hwnd) -> None:
        u = self.user32
        popup = u.CreatePopupMenu()
        try:
            for i, item in enumerate(self.menu, start=1):
                if item is None:
                    u.AppendMenuW(popup, MF_SEPARATOR, 0, None)
                else:
                    u.AppendMenuW(popup, MF_STRING, i, item[0])
            pt = w.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            u.SetForegroundWindow(hwnd)  # without it the menu stays open after a click elsewhere
            chosen = u.TrackPopupMenu(popup, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
                                      pt.x, pt.y, 0, hwnd, None)
            u.PostMessageW(hwnd, WM_NULL, 0, 0)
        finally:
            u.DestroyMenu(popup)
        if 1 <= chosen <= len(self.menu) and (item := self.menu[chosen - 1]):
            self._safe(item[0], item[1])

    def _safe(self, what: str, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception:
            log.exception("tray: %s failed", what)

    def _load_icon(self):
        u = self.user32
        if self.icon_path and self.icon_path.is_file():
            side = u.GetSystemMetrics(SM_CXSMICON)  # the tray's size at this screen's scaling
            if icon := u.LoadImageW(None, str(self.icon_path), IMAGE_ICON, side, side, LR_LOADFROMFILE):
                return icon
        return u.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _data(self, flags: int, hwnd=None) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=hwnd or self.hwnd, uID=1)
        data.uFlags = flags
        return data


def create(tooltip: str, menu: list[MenuItem], on_open: Callable[[], None], icon: Path | None = None,
           on_quit: Callable[[], None] | None = None) -> Tray | None:
    """Start the icon; None off Windows or when Windows refused it (the caller then runs without one)."""
    if os.name != "nt":
        return None
    tray = Tray(tooltip, menu, on_open, icon, on_quit)
    return tray if tray.start() else None


def ask_running_to_open() -> bool:
    """If DevExAI already runs in the tray, ask it to open the dashboard and return True."""
    if os.name != "nt":
        return False
    user32, _, _ = _api()
    hwnd = user32.FindWindowW(CLASS, None)
    return bool(hwnd) and bool(user32.PostMessageW(hwnd, OPEN_REQUEST, 0, 0))


def show_error(title: str, text: str) -> None:
    """A message box, for errors in the windowed build where there is no console to print to."""
    if os.name == "nt":
        _api()[0].MessageBoxW(None, text, title, MB_ICONERROR)
    else:
        print(f"{title}: {text}", file=sys.stderr)
