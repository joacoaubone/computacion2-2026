import os
import signal
import select


_r_fd = None
_w_fd = None


def _handler(signum, frame):
    os.write(_w_fd, bytes([signum]))


def setup_señales():
    global _r_fd, _w_fd
    _r_fd, _w_fd = os.pipe()
    os.set_blocking(_r_fd, False)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP,
                signal.SIGUSR1, signal.SIGUSR2, signal.SIGWINCH):
        signal.signal(sig, _handler)


def recibir_señales(timeout=0.1):
    if _r_fd is None:
        return None
    ready, _, _ = select.select([_r_fd], [], [], timeout)
    if ready:
        data = os.read(_r_fd, 1)
        if data:
            return data[0]
    return None
