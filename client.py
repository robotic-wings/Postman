
import os
import sys
import hmac
from pathlib import Path
from postman_client import PostmanClient, Transaction
from utils import read_config, client_log, encode_base64_msg

# This is just a sample pair of ID and Secret
PERSONAL_ID = '7D444D'
PERSONAL_SECRET = 'b4b52156ba5213240a2315b0bc5412ed'


def main(eaves_mode = False):
    if len(sys.argv) != 2:
        exit(1)
    cfg = read_config(sys.argv[1])
    if "server_port" not in cfg or "send_path" not in cfg:
        exit(2)
    send_path = os.path.expanduser(cfg["send_path"])
    if not cfg["server_port"].isdigit() or not os.path.isdir(send_path):
        exit(2)
    if eaves_mode:
        server_port = int(cfg["client_port"])  # eavesdropper testing
    else:
        server_port = int(cfg["server_port"])
    send_list = sorted(os.listdir(send_path))
    for file in send_list:
        pm_client = PostmanClient("127.0.0.1", server_port)
        file_path = Path(send_path) / file
        send_file = open(str(file_path), mode="r", encoding="utf-8")
        try:
            txn = Transaction.read_text(send_file.read())
            if txn.check_formation():
                pm_client.connect()
                pm_client.receive()
                ehlo_resp = pm_client.run("EHLO", "127.0.0.1")
                if "auth" in str(file_path) and "CRAM-MD5" in ehlo_resp:
                    pm_client.run("AUTH", "CRAM-MD5")
                    _, server_challenge = pm_client.receive()
                    digester = hmac.new(PERSONAL_SECRET.encode("ascii"), \
                        msg=server_challenge.encode("ascii"), digestmod='md5')
                    to_send = encode_base64_msg(PERSONAL_ID + " " + digester.hexdigest())
                    pm_client.send(to_send)
                    pm_client.receive()
                pm_client.send_email(txn)
                pm_client.run("QUIT")
                pm_client.disconnect()
                pm_client.print_client_log()
            else:
                client_log(str(file_path.absolute()) + ": Bad formation")
        except ConnectionResetError:
            pm_client.print_client_log()
            client_log("Connection lost")
            exit(3)
        except ConnectionRefusedError:
            pm_client.print_client_log()
            client_log("Cannot establish connection")
            exit(3)
        send_file.close()

if __name__ == '__main__':
    main()
