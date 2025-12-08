import ctypes
from ctypes import wintypes
import time

# Windows API constants
GW_HWNDFIRST = 0
GW_HWNDNEXT = 2
GW_OWNER = 4
WS_VISIBLE = 0x10000000

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_active_window_info():
    try:
        hwnd = user32.GetForegroundWindow()
        
        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        window_title = buff.value
        
        # Get process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        return f"PID_{pid.value}", window_title
    except Exception:
        return None, None

if __name__ == "__main__":
    last_app = None
    while True:
        current_app, window_title = get_active_window_info()
        if current_app and current_app != last_app:
            print(f"Active application: {current_app} - {window_title}")
            last_app = current_app
        time.sleep(1)



