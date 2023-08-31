
import socket
import regex
from utils import is_smtp_message, server_log, client_log
from postman_states import PostmanStates
from postman_transaction import Transaction


class PostmanClient:
    """The Postman SMTP Client

    Raises:
        ConnectionResetError: Connection reset by the server
    """
    buffer: str
    cli: socket.socket
    evil_mode: bool
    current_state: PostmanStates
    my_msgs: list
    peer_msgs: list

    def receive(self) -> list:
        """Receive a message from the server.

        Raises:
            ConnectionResetError: Connection reset by the server

        Returns:
            list: The server response as a list of parameters
        """
        resp = self.cli.recv(1024).decode("ascii")
        if not is_smtp_message(resp):
            raise ConnectionResetError("client")
        resp_re = regex.compile(r"(([0-7]{3})(\s(.+)(\r\n)*)*)\r\n")
        resp_match = resp_re.match(resp)
        assert resp_match is not None, "bad server response" # however it should not happen
        msg = resp_match.captures(1)[0]   # real SERVER response
        self.peer_msgs.append(msg)
        resp_code, resp_params = resp_match.captures(2)[0], resp_match.captures(4)
        self.current_state = PostmanStates(resp_code)
        return resp_params

    def __init__(self, address: str, port: int, evil_mode: bool = False):
        """Initialise the Postman Client.

        Args:
            address (str): The address of the target server.
            port (int): The port of the target server.
            evil_mode (bool, optional): Whether the client acts as an agent
            to transmit data from the eavesdropper to the real server. Defaults to False.
        """
        self.address = address
        self.port = port
        self.evil_mode = evil_mode
        self.my_msgs = []
        self.peer_msgs = []

    def send(self, message: str):
        """Send a message to the target server.

        Args:
            message (str): The whole message string
        """
        self.cli.send(message.encode("ascii"))

    def run(self, cmd: str, *params: str) -> list:
        """Send a command line and get feedback in the interactive SMTP session.

        Args:
            cmd (str): command name
            *args (str): arguments

        Returns:
            list: The server response as a list of parameters
        """
        message = cmd + (" " if len(params) > 0 else "") + " ".join(params)
        return self.request(message)

    def request(self, message: str) -> list:
        """Send a line and get feedback in the interactive SMTP session.
           A carriage return will be added for you

        Args:
            message (str): The whole message

        Returns:
            list: The server response as a list of parameters
        """
        # The message is a real CLIENT message
        self.my_msgs.append(message)
        self.send(message + "\r\n")
        return self.receive()

    def send_email(self, transaction_data: Transaction):
        """Send an email to the SMTP server.

        Args:
            transaction_data (Transaction): The transaction object
        """
        self.run("MAIL", f"FROM:<{transaction_data.sender}>")
        for recipient in transaction_data.recipients:
            self.run("RCPT", f"TO:<{recipient}>")
        self.run("DATA")
        if hasattr(transaction_data, "created_time_rfc5322"):
            self.request("Date: " + transaction_data.created_time_rfc5322)
        if hasattr(transaction_data, "subject"):
            self.request("Subject: " + transaction_data.subject)
        for line_text in transaction_data.content:
            self.request(line_text)
        self.request(".")

    def connect(self):
        """Connect to the specified server
        """
        self.cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cli.connect((self.address, self.port))

    def disconnect(self):
        """Disconnect from the server
        """
        self.cli.close()

    def print_client_log(self):
        """Dump all log generated in client-server interactions to stdout.
        """
        while True:
            try:
                server_log(self.peer_msgs.pop(0))
                client_log(self.my_msgs.pop(0))
            except IndexError:
                break
