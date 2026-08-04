import json
import socket
from typing import Any


MAX_MESSAGE_SIZE = 1024 * 1024


def encode_message(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def send_message(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(encode_message(payload))


def read_message(sock: socket.socket) -> dict[str, Any]:
    chunks = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("connection closed before complete zone message")
        chunks.extend(chunk)
        if len(chunks) > MAX_MESSAGE_SIZE:
            raise ValueError("zone message exceeded maximum size")
        if b"\n" in chunk:
            line, _, _rest = bytes(chunks).partition(b"\n")
            return json.loads(line.decode("utf-8"))
