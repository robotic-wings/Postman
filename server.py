'''
Name: Kefan Liu
UniKey: kliu9014
SID: 500135385
'''
import os
import sys
import socket
from utils import read_config, server_log
from postman_server import PostmanServer

PERSONAL_ID = '7D444D'
PERSONAL_SECRET = 'b4b52156ba5213240a2315b0bc5412ed'


def main():
    cfg = read_config(sys.argv[1])
    if "server_port" not in cfg or "inbox_path" not in cfg:
        exit(2)
    inbox_path = os.path.expanduser(cfg["inbox_path"])
    if not cfg["server_port"].isdigit() or not os.path.isdir(inbox_path):
        exit(2)
    server_port = int(cfg["server_port"])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("localhost", server_port))
    server.listen(5)
    while True:
        pm_server = PostmanServer(inbox_path)
        pm_server.set_credential(PERSONAL_ID, PERSONAL_SECRET)
        try:
            conn, _ = server.accept()
            pm_server.run(conn)
            pm_server.print_server_log()
        except KeyboardInterrupt:
            server_log("SIGINT received, closing")
            exit(0)
        except ConnectionResetError:
            pm_server.print_server_log()
            server_log("Connection lost")

if __name__ == '__main__':
    main()
