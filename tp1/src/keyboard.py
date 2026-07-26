import sys
import os
import select
import termios


_old_settings = None
_fd = None


def entrar_modo_raw():
    global _old_settings, _fd
    try:
        _fd = sys.stdin.fileno()
        _old_settings = termios.tcgetattr(_fd)
        attrs = termios.tcgetattr(_fd)
        attrs[0] &= ~(termios.ICRNL | termios.INLCR | termios.IGNCR)
        attrs[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(_fd, termios.TCSANOW, attrs)
    except (termios.error, OSError):
        pass


def salir_modo_raw():
    global _old_settings
    if _old_settings is not None:
        try:
            termios.tcsetattr(_fd, termios.TCSADRAIN, _old_settings)
        except (termios.error, OSError):
            pass
        _old_settings = None


def _leer_bytes(n, timeout):
    r, _, _ = select.select([_fd], [], [], timeout)
    if r:
        return os.read(_fd, n)
    return b''


def leer_tecla(timeout=0.25):
    try:
        buf = _leer_bytes(1, timeout)
        if not buf:
            return None
        ch = chr(buf[0])
        if ch == '\x1b':
            return _consumir_escape()
        if ch == '\r':
            return 'KEY_ENTER'
        if ch == '\x03':
            return 'KEY_CTRLC'
        if ch == '\x7f':
            return 'KEY_BACKSPACE'
        if ord(ch) < 32:
            return None
        return ch
    except (ValueError, OSError):
        pass
    return None


def _consumir_escape():
    buf = _leer_bytes(16, 0.1)
    seq = '\x1b' + ''.join(chr(b) for b in buf)
    if seq in ('\x1b[A', '\x1bOA'):
        return 'KEY_UP'
    if seq in ('\x1b[B', '\x1bOB'):
        return 'KEY_DOWN'
    if seq in ('\x1b[C', '\x1bOC'):
        return 'KEY_RIGHT'
    if seq in ('\x1b[D', '\x1bOD'):
        return 'KEY_LEFT'
    if len(seq) == 1:
        return 'ESC'
    return seq
