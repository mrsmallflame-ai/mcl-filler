#!/usr/bin/env python3
"""Tiny stdlib-only SOCKS5 server (CONNECT only, no auth). Listens on 127.0.0.1.

Used by mac-relay.sh: runs on the Mac so the VPS can borrow its residential IP
via `ssh -R`, bypassing MCL's datacenter/WARP IP ban. No dependencies.
"""
import socket
import socketserver
import struct
import sys
import threading


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed mid-handshake")
        buf += chunk
    return buf


def handle_socks(conn):
    try:
        ver, nmethods = _recv_exact(conn, 2)
        _recv_exact(conn, nmethods)
        conn.sendall(b"\x05\x00")                    # choose "no auth"
        req = _recv_exact(conn, 4)
        cmd, atyp = req[1], req[3]
        if cmd != 1:                                  # only CONNECT
            conn.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
            return
        if atyp == 1:
            addr = socket.inet_ntoa(_recv_exact(conn, 4))
        elif atyp == 3:
            ln = _recv_exact(conn, 1)[0]
            addr = _recv_exact(conn, ln).decode()
        elif atyp == 4:
            addr = socket.inet_ntop(socket.AF_INET6, _recv_exact(conn, 16))
        else:
            conn.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
            return
        (port,) = struct.unpack(">H", _recv_exact(conn, 2))

        try:
            remote = socket.create_connection((addr, port), timeout=15)
        except Exception:
            conn.sendall(b"\x05\x01\x00\x01" + b"\x00" * 6)
            return
        conn.sendall(b"\x05\x00\x00\x01" + b"\x00" * 4 + struct.pack(">H", 0))
    except Exception:
        conn.close()
        return

    def pump(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    t = threading.Thread(target=pump, args=(remote, conn), daemon=True)
    t.start()
    pump(conn, remote)
    t.join(timeout=2)
    remote.close()
    conn.close()


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        handle_socks(self.request)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1080
    bind = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    print(f"SOCKS5 (no auth) on {bind}:{port}", flush=True)
    Server((bind, port), Handler).serve_forever()
