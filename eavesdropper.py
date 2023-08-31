
import os
import sys
import socket
from postman_client import PostmanClient
from utils import read_config, client_log, server_log
from postman_server import PostmanServer

def main():
    if len(sys.argv) != 2:
        exit(1)
    cfg = read_config(sys.argv[1])
    for cfg_key in ["server_port", "spy_path", "client_port"]:
        if cfg_key not in cfg:
            exit(2)
    spy_path = os.path.expanduser(cfg["spy_path"])
    if not cfg["server_port"].isdigit() \
    or not cfg["client_port"].isdigit() \
    or not os.path.isdir(spy_path):
        exit(2)
    client_port = int(cfg["client_port"])
    server_port = int(cfg["server_port"])
    # agent talks to the real server on behalf of the real client
    agent = PostmanClient("localhost", server_port, True)
    # false server cheats the real client
    false_server = PostmanServer(spy_path, agent)
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("localhost", client_port))
        server.listen(5)
        conn, _ = server.accept()
        false_server.run(conn)
        false_server.print_server_log()
        exit(0)
    except ConnectionResetError:
        false_server.print_server_log()
        client_log("Connection lost", True)
    except ConnectionRefusedError:
        false_server.print_server_log()
        server_log("Cannot establish connection", True)
        exit(3)

if __name__ == '__main__':
    main()
