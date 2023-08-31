
import base64
import datetime
import time
import regex

def decode_base64_msg(base64_message: str) -> str:
    """Decode a base64 string using ASCII

    Args:
        base64_message (str): The base64 string

    Returns:
        str: The decoded message
    """
    base64_bytes = base64_message.encode('ascii')
    message_bytes = base64.b64decode(base64_bytes)
    message = message_bytes.decode('ascii')
    return message

def encode_base64_msg(message: str) -> str:
    """Encode a message into a base64 string

    Args:
        message (str): The message to be encoded

    Returns:
        str: The base64 string
    """
    message_bytes = message.encode('ascii')
    base64_bytes = base64.b64encode(message_bytes)
    base64_message = base64_bytes.decode("ascii")
    return base64_message

def check_email_addr(addr: str) -> bool:
    """Check if an email address is valid

    Args:
        addr (str): the email address

    Returns:
        bool: vaildity
    """
    letdig = r"[A-Za-z0-9]"
    atom = r"[A-Za-z0-9][A-Za-z0-9-]*"
    ipv4_addr_literal = r"[1-9][0-9]{1,2}(\.[1-9][0-9]{1,2}){3}"
    address_literal = rf"\[{ipv4_addr_literal}\]"
    ldh_str = r"[A-Za-z0-9-]*" + letdig
    sub_domain = rf"{letdig}({ldh_str})?"
    domain = rf"({sub_domain}(\.{sub_domain})+|{address_literal})"
    dot_string = rf"{atom}(\.{atom})*"
    mailbox = rf"{dot_string}@{domain}"
    re_match = regex.compile(mailbox).match(addr)
    return re_match is not None

def parse_rfc5322_time(rfc5322_time: str) -> datetime.datetime | None:
    """Parse an rfc5322 time string into datetime object.

    Args:
        string_time (str): rfc5322 time string

    Returns:
        datetime.datetime | None: Returns a datetime object if the time string is valid,
        otherwise returns None
    """
    re_match = regex.compile((r"(((Mon|Tue|Wed|Thu|Fri|Sat|Sun))[,]?"
                             r"\s([0-9]{1,2}))"
                             r"\s(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                             r"\s([0-9]{4})\s([0-9]{2}):([0-9]{2})(:([0-9]{2}))?"
                             r"\s([\+|\-][0-9]{4})\s?")) \
                                .match(rfc5322_time)
    if re_match is not None:
        day, month, year, hour, minute, _, second, timezone = \
            [re_match.captures(i)[0] for i in range(4,12)]
        tz_sign, tz_h, tz_m = -1 if timezone[0] == "-" else 1, \
            int(timezone[1:3]), int(timezone[3:5])
        tzinfo = datetime.timezone(tz_sign * datetime.timedelta(hours=tz_h, minutes=tz_m))
        return datetime.datetime(int(year), time.strptime(month, "%b").tm_mon, \
            int(day), int(hour), int(minute), int(second), 0, tzinfo)

def read_config(config_path: str) -> dict:
    """Read a configuration file.

    Args:
        config_path (str): config file path

    Returns:
        dict: A set of preferences
    """
    config_data = {}
    file_obj = open(config_path, mode="r", encoding="utf-8")
    for config_line in file_obj.readlines():
        if "=" in config_line:
            key, value = config_line.strip().split("=", 1)
            config_data[key] = value
    return config_data

def server_log(msg: str, spy: bool = False, prefix: str = ""):
    """Log a line with the server prefix

    Args:
        msg (str): the message to be logged
        spy (bool, optional): whether it's from the eavesdropper. Defaults to False.
        prefix (str, optional): The custom prefix before "S:". Defaults to "".
    """
    for line_msg in msg.split("\r\n"):
        print(prefix + ("A" if spy else "") + "S: " + line_msg, end="\r\n", flush=True)

def client_log(msg: str, spy: bool = False, prefix: str = ""):
    """Log a line with the client prefix

    Args:
        msg (str): the message to be logged
        spy (bool, optional): whether it's from the eavesdropper. Defaults to False.
        prefix (str, optional): The custom prefix before "S:". Defaults to "".
    """
    for line_msg in msg.split("\r\n"):
        print(prefix + ("A" if spy else "") + "C: " + line_msg, end="\r\n", flush=True)

def is_smtp_message(msg: str):
    """Check if the message is an SMTP one (ends with a carriage return)

    Args:
        msg (str): The message to check

    Returns:
        bool: True for the message ends with a carriage return
    """
    return len(msg) >= 2 and msg[-2] + msg[-1] == "\r\n"
    
