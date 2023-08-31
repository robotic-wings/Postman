
import socket
from secrets import token_hex
import hmac
from typing import TYPE_CHECKING
import regex
from postman_states import PostmanStates
from utils import server_log, is_smtp_message, client_log, decode_base64_msg, \
    check_email_addr, encode_base64_msg
from postman_transaction import Transaction
if TYPE_CHECKING:
    from postman_client import PostmanClient

class PostmanServer:
    """A SMTP Server that uses CRAM-MD5 as the authentication protocol.

    Raises:
        ConnectionResetError: When the connection is reset by the client.
    """
    current_state: PostmanStates
    client_hostname: str
    server_port: int
    conn: socket.socket
    uid: str
    secret: str
    challenge: str
    inbox_dir_path: str
    txn: Transaction | None
    in_header: bool
    evil_mode: bool
    agent: "PostmanClient"
    my_msgs: list
    peer_msgs: list
    instant_logging: bool

    def __init__(self, inbox_dir_path: str, agent = None, instant_logging: bool = False):
        """Initialize a Postman server.

        Args:
            inbox_dir_path (str): Where to store the received emails
            agent (Any, optional): The agent for talking with the real server
            if this instance is used as an eavesdropper. Defaults to None.
            instant_logging (bool, optional): True for logging instantly rather than dumping logs
            when the client session ends. Defaults to False.
        """
        self.inbox_dir_path = inbox_dir_path
        self.txn = None
        self.my_msgs = []
        self.peer_msgs = []
        self.client_quit = False
        if agent is not None:
            self.agent = agent
            self.evil_mode = True
        else:
            self.evil_mode = False
        self.instant_logging = instant_logging

    def set_credential(self, uid: str, secret: str):
        """Set the credential for this server.
           When the method is called, the server instance is assumed to be the real server.
        Args:
            uid (str): The Personal ID
            secret (str): The Personal Secret
        """
        self.uid = uid
        self.secret = secret

    def set_multiprocess_info(self, pid: int, order: int):
        """Set the process info for a child of the multiprocess server.
           Calling this method sets the prefix of logging lines.
        Args:
            pid (int): The PID of the child process server
            order (int): The order of the child process server
        """
        self.pid = pid
        self.order = order

    @property
    def prefix(self) -> str:
        """Get the prefix of logging lines.

        Returns:
            str: Empty when the server is not for multiprocessing, or includes PID and order.
        """
        if hasattr(self, "pid") and hasattr(self, "order"):
            return f"[{self.pid}][{str(self.order).zfill(2)}]"
        else:
            return ""

    def respond(self, *message: str):
        """Send a response to the client.
        Args:
            *message (str): Messages to send to the client.
            They will be joined by carriage returns before sent.
        """
        self.conn.sendall(("\r\n".join(message)+"\r\n").encode("ascii"))
        if self.instant_logging:
            server_log("\r\n".join(message), prefix=self.prefix)
        else:
            self.my_msgs.append("\r\n".join(message))

    def run(self, client: socket.socket):
        """Start running the server.

        Args:
            client (socket.socket): A client socket from accept

        Raises:
            ConnectionResetError: Connection is reset by the client
        """
        self.conn = client
        if self.evil_mode:
            self.agent.connect()
        self.transit(PostmanStates.SERVICE_READY)
        while True:
            try:
                if self.client_quit:
                    break
                # auto replace all \n with \r\n to make the server compatible with netcat
                client_msg = self.conn.recv(2048).decode("ascii")
                client_msg = client_msg.replace("\r\n", "\n")
                client_msg = client_msg.replace("\n", "\r\n")
                if is_smtp_message(client_msg):
                    # remove ONE carriage return at the end of message
                    client_msg = client_msg[0:-2]
                    if self.evil_mode:   # AS
                        self.agent.request(client_msg)
                    if self.instant_logging:
                        client_log(client_msg, prefix=self.prefix)
                    else:
                        self.peer_msgs.append(client_msg)
                    cur_state = self.current_state
                    if cur_state == PostmanStates.SERVER_BASE64_ENCODED_CHALLENGE:
                        # authentication process
                        # dealing with client's uid + challenge
                        if not self.evil_mode:
                            received = decode_base64_msg(client_msg)
                            assert received != "*", \
                                PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
                            uid, hashed_secret = received.split(" ", 1)
                            digester = hmac.new(self.secret.encode(
                                "ascii"), msg=self.challenge.encode("ascii"), digestmod='md5')
                            if uid == self.uid and digester.hexdigest() == hashed_secret:
                                # auth success
                                self.transit(PostmanStates.AUTHENTICATION_SUCCEEDED)
                            else:
                                # auth failed
                                self.transit(
                                    PostmanStates.AUTHENTICATION_CREDENTIALS_INVALID)
                        else:
                            # The agent (client) syncs the current state with the real server.
                            self.transit(self.agent.current_state)
                    elif cur_state == PostmanStates.START_MAIL_INPUT:
                        if self.txn is None:
                            raise IOError(
                                "In start mail input mode BUT txn is None")
                        # input mail data
                        if client_msg == ".":  # ending an email transaction
                            if self.txn.check_formation():
                                self.txn.save_as(self.inbox_dir_path, self.prefix)
                            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY)
                        else:  # appending an email transaction
                            self.in_header = self.txn.add_entry(client_msg, self.in_header)
                            self.transit(PostmanStates.START_MAIL_INPUT)
                    else:
                        # run command
                        # 500 no command's length is less than 4
                        assert len(client_msg) >= 4, PostmanStates.COMMAND_UNRECOGNIZED
                        self.run_command(client_msg[0:4], client_msg[4:])
                else:
                    raise ConnectionResetError("server")
            except AssertionError as err:
                self.transit(err.args[0])

    def run_command(self, cmd: str, arg_str: str):
        """Run a command line from the client.

        Args:
            cmd (str): Command name
            arg_str (str): The whole argument string
        """
        args = [arg for arg in arg_str.split() if len(arg) > 0]
        if cmd == "EHLO":
            # guardians
            # must have one IPv4 address as the only parameter
            ipv4_regex = regex.compile(r"[0-9]{1,3}(\.[0-9]{1,3}){3}")
            assert len(args) == 1 and ipv4_regex.match(
                args[0]) is not None, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.client_hostname = args[0]
            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY, ehlo=True)
        elif cmd == "AUTH":
            # guardians
            assert len(
                args) == 1, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            assert args[0] == "CRAM-MD5", PostmanStates.COMMAND_PARAMETER_NOT_IMPLEMENTED
            # main job
            self.transit(PostmanStates.SERVER_BASE64_ENCODED_CHALLENGE)
        elif cmd == "QUIT":
            # guardians
            # 501 exactly no argument
            assert len(
                arg_str) == 0, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.transit(PostmanStates.SERVICE_CLOSING_TRANSIMISSION_CHANNEL)
        elif cmd == "MAIL":
            # guardians
            # 503 hostname
            assert hasattr(
                self, "client_hostname"), PostmanStates.BAD_SEQUENCE_OF_COMMANDS
            # 503 txn object doesn't exist
            assert self.txn is None, PostmanStates.BAD_SEQUENCE_OF_COMMANDS
            # 501 exactly one argument
            assert len(
                args) == 1, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # 501 command grammar
            re_match = regex.compile(r"FROM:<(.+)>").match(args[0])
            assert re_match is not None, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # 501 email address
            email_addr = re_match.captures(1)[0]
            assert check_email_addr(
                email_addr), PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.in_header = True
            self.txn = Transaction()
            self.txn.sender = email_addr
            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY)
        elif cmd == "RCPT":
            # guardians
            # 503 txn object does not exist
            assert self.txn is not None, PostmanStates.BAD_SEQUENCE_OF_COMMANDS
            # 501 exactly one argument
            assert len(
                args) == 1, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            re_match = regex.compile(r"TO:<(.+)>").match(args[0])
            # 501 command grammar
            assert re_match is not None, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            email_addr = re_match.captures(1)[0]
            # 501 email address
            assert check_email_addr(
                email_addr), PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.txn.recipients.append(email_addr)
            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY)
        elif cmd == "DATA":
            # guardians
            # 503 txn object exists
            assert self.txn is not None, PostmanStates.BAD_SEQUENCE_OF_COMMANDS
            # 501 exactly no argument
            assert len(
                arg_str) == 0, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.transit(PostmanStates.START_MAIL_INPUT)  # 354
        elif cmd == "RSET":
            # guardians
            # 501 exactly no arguemnt
            assert len(
                arg_str) == 0, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.txn = None
            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY)
        elif cmd == "NOOP":
            # guardians
            # 501 exactly no argument
            assert len(
                arg_str) == 0, PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS
            # main job
            self.transit(PostmanStates.REQUEST_MAIL_ACTION_OKAY)
        else:
            self.transit(PostmanStates.COMMAND_UNRECOGNIZED)

    def transit(self, new_st: PostmanStates, **args):
        """Transit from the current state to a new state, as well as make according changes.

        Args:
            new_state (PostmanStates): The target new state
        """
        self.current_state = new_st
        if new_st == PostmanStates.SERVICE_READY:
            self.respond("220 Service ready")
        elif new_st == PostmanStates.REQUEST_MAIL_ACTION_OKAY:
            if args.get("ehlo") is True:
                self.respond("250 127.0.0.1",
                             "250 AUTH CRAM-MD5")
            else:
                self.respond("250 Requested mail action okay completed")
        elif new_st == PostmanStates.SERVICE_CLOSING_TRANSIMISSION_CHANNEL:
            self.respond("221 Service closing transmission channel")
            if self.evil_mode:
                self.agent.receive()   # receive "221 Service closing transmission channel"
            self.conn.close()
            self.client_quit = True
        elif new_st == PostmanStates.SERVER_BASE64_ENCODED_CHALLENGE:
            # generate a challenge for the client
            # this backdoor is permitted by Michael as per the Ed post #1818 for E2E testing
            if self.client_hostname == "1.2.3.4":
                self.challenge = "12345678-1234-1234-1234-1234567890ab"
            else:
                self.challenge = \
                    f"{token_hex(4)}-{token_hex(2)}-{token_hex(2)}-{token_hex(2)}-{token_hex(6)}"
            challenge_base64 = encode_base64_msg(self.challenge)
            self.respond("334 " + challenge_base64)
        elif new_st == PostmanStates.AUTHENTICATION_SUCCEEDED:
            self.respond("235 Authentication successful")
        elif new_st == PostmanStates.AUTHENTICATION_CREDENTIALS_INVALID:
            self.respond("535 Authentication credentials invalid")
        elif new_st == PostmanStates.COMMAND_UNRECOGNIZED:
            self.respond("500 Syntax error, command unrecognized")
        elif new_st == PostmanStates.BAD_SEQUENCE_OF_COMMANDS:
            self.respond("503 Bad sequence of commands")
        elif new_st == PostmanStates.COMMAND_PARAMETER_NOT_IMPLEMENTED:
            self.respond("504 Command parameter not implemented")
        elif new_st == PostmanStates.SYNTAX_ERROR_IN_PARAMETERS_OR_ARUGUMENTS:
            self.respond("501 Syntax error in parameters or arguments")
        elif new_st == PostmanStates.START_MAIL_INPUT:
            self.respond("354 Start mail input end <CRLF>.<CRLF>")

    def print_server_log(self):
        """Dump all logs of the server instance.
        """
        while True:
            try:
                server_log(self.my_msgs.pop(0), prefix=self.prefix)  # S
                if self.evil_mode:
                    client_log(self.agent.peer_msgs.pop(0), spy=True, prefix=self.prefix)  # AC
                client_log(self.peer_msgs.pop(0), prefix = self.prefix) # C
                if self.evil_mode:
                    server_log(self.agent.my_msgs.pop(0), True, prefix=self.prefix) # AS
            except IndexError:
                break
