import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

FILE_READ_ATTRIBUTES = 0x0080
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
IO_REPARSE_TAG_SYMLINK = 0xA000000C
FSCTL_GET_REPARSE_POINT = 0x000900A8
MAXIMUM_REPARSE_DATA_BUFFER_SIZE = 0x4000

LPDWORD = ctypes.POINTER(wintypes.DWORD)
LPWIN32_FIND_DATA = ctypes.POINTER(wintypes.WIN32_FIND_DATAW)
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def IsReparseTagNameSurrogate(tag):
    return bool(tag & 0x20000000)


def _check_invalid_handle(result, func, args):
    if result == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return args


def _check_bool(result, func, args):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return args


def islink(path):
    data = wintypes.WIN32_FIND_DATAW()
    kernel32.FindClose(kernel32.FindFirstFileW(path, ctypes.byref(data)))
    if not data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
        return False
    return IsReparseTagNameSurrogate(data.dwReserved0)
