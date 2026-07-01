import socket
import sys
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
RECV_TIMEOUT_SEC = 600


def main():
    if len(sys.argv) < 2:
        print("usage:")
        print(r"& C:\isaacsim\python.bat C:\VScode\Yoshida_script\send_to_isaac.py C:\VScode\Yoshida_script\scripu2.py")
        raise SystemExit(1)

    script_path = Path(sys.argv[1])
    if not script_path.exists():
        raise FileNotFoundError(script_path)

    code = script_path.read_text(encoding="utf-8")

    with socket.create_connection((HOST, PORT), timeout=10) as sock:
        sock.settimeout(RECV_TIMEOUT_SEC)
        sock.sendall(code.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)

    result = b"".join(chunks).decode("utf-8", errors="replace")
    print(result)


if __name__ == "__main__":
    main()

