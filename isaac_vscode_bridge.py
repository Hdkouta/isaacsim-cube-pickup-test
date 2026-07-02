import builtins
import contextlib
import io
import queue
import socket
import threading
import traceback

import omni.kit.app

HOST = "127.0.0.1"
PORT = 8765
EXEC_TIMEOUT_SEC = 900

if getattr(builtins, "_ISAAC_VSCODE_BRIDGE_RUNNING", False):
    print("Isaac VSCode bridge is already running")
else:
    builtins._ISAAC_VSCODE_BRIDGE_RUNNING = True

    EXEC_GLOBALS = {"__name__": "__isaac_vscode_exec__"}
    request_queue = queue.Queue()

    def execute_on_update(event):
        while not request_queue.empty():
            item = request_queue.get()
            code = item["code"]
            done = item["done"]

            stdout = io.StringIO()
            stderr = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exec(code, EXEC_GLOBALS, EXEC_GLOBALS)

                output = stdout.getvalue()
                err = stderr.getvalue()
                if err:
                    output += "\n[stderr]\n" + err
                item["result"] = output if output.strip() else "[done]"
            except Exception:
                item["result"] = stdout.getvalue()
                item["result"] += "\n[exception]\n"
                item["result"] += traceback.format_exc()

            done.set()

    update_stream = omni.kit.app.get_app().get_update_event_stream()
    builtins._ISAAC_VSCODE_BRIDGE_SUB = update_stream.create_subscription_to_pop(
        execute_on_update,
        name="isaac_vscode_bridge_update",
    )

    def handle_client(conn):
        try:
            chunks = []
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                chunks.append(data)

            code = b"".join(chunks).decode("utf-8")
            done = threading.Event()
            item = {"code": code, "done": done, "result": ""}
            request_queue.put(item)

            if not done.wait(timeout=EXEC_TIMEOUT_SEC):
                result = f"[timeout] script did not finish within {EXEC_TIMEOUT_SEC} seconds"
            else:
                result = item["result"]

            conn.sendall(result.encode("utf-8", errors="replace"))
        except Exception:
            conn.sendall(traceback.format_exc().encode("utf-8", errors="replace"))
        finally:
            conn.close()

    def server_loop():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)

        print(f"Isaac VSCode bridge listening on {HOST}:{PORT}")

        while True:
            conn, _ = server.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

    threading.Thread(target=server_loop, daemon=True).start()
    print("Isaac VSCode bridge started")
