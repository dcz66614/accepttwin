"""Direct unit tests for the runner's port check (P032 T005, step 05).

:func:`accepttwin.experiment_runner._check_port_listening` is the
live check behind step 05 (VerifyLocalPorts); these tests exercise
it directly with a real listening socket, no stubs.
"""

from __future__ import annotations

import socket

from accepttwin.experiment_runner import _check_port_listening


def test_check_port_listening_true_for_listening_socket():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        port = server.getsockname()[1]
        assert _check_port_listening("127.0.0.1", port) is True
    finally:
        server.close()


def test_check_port_listening_false_for_dead_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert _check_port_listening("127.0.0.1", port) is False
