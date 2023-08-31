'''
Name: Kefan Liu
UniKey: kliu9014
SID: 500135385
'''
import os
import sys
import socket
import signal
from utils import read_config, server_log
from postman_server import PostmanServer


# Visit https://edstem.org/au/courses/8961/lessons/26522/slides/196175 to get
PERSONAL_ID = '7D444D'
PERSONAL_SECRET = 'b4b52156ba5213240a2315b0bc5412ed'

def main():
    children: list = []
    order: int = 0
    pid: int = os.getpid()
    try:
        cfg = read_config(sys.argv[1])
        if "server_port" not in cfg or "inbox_path" not in cfg:
            exit(2)
        inbox_path = os.path.expanduser(cfg["inbox_path"])
        if not cfg["server_port"].isdigit() or not os.path.isdir(inbox_path):
            exit(2)
        server_port = int(cfg["server_port"])
        manager = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        manager.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        manager.bind(("localhost", server_port))
        manager.listen(5)
        while True:
            # accept() MUST be blocking or your computer goes to the hell
            client, _ = manager.accept()
            pid = os.fork()
            if pid == 0:  # child process
                staff = PostmanServer(inbox_path, instant_logging=True)
                staff.set_credential(PERSONAL_ID, PERSONAL_SECRET)
                staff.set_multiprocess_info(os.getpid(), order + 1)
                try:
                    staff.run(client)
                except ConnectionResetError:
                    server_log("Connection lost", prefix=staff.prefix)
                finally:
                    exit()   # the child process MUST terminate or your computer goes to the hell
            else:
                order += 1
                children.append(pid)
        manager.close()
    except KeyboardInterrupt:
        if pid > 0:   # parent process
            for child_pid in children:
                os.kill(child_pid, signal.SIGINT)
        exit()

if __name__ == '__main__':
    main()
