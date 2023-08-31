'''
Name: Kefan Liu
UniKey: kliu9014
SID: 500135385
'''
from pathlib import Path
import datetime
import time
import regex
from utils import parse_rfc5322_time

class Transaction:
    """A single e-mail transaction data object.
    """
    sender: str
    recipients: list
    created_time: datetime.datetime
    created_time_rfc5322: str
    subject: str
    content: list[str]

    def __init__(self):
        self.recipients = []
        self.content = []

    def check_formation(self):
        """Check if the sender and recipient fields both exist.

        Returns:
            bool: True for good formation, False for bad formation
        """
        # the sender and recipient field are mandatory
        return hasattr(self, "sender") and len(self.recipients) > 0

    def set_created_time(self, rfc5322: str):
        """Set the created time for the current transaction object.

        Args:
            rfc5322 (str): An rfc5322 time string
        """
        parsed = parse_rfc5322_time(rfc5322)
        if parsed is not None:
            self.created_time = parsed
            self.created_time_rfc5322 = rfc5322

    def add_entry(self, text_line: str, allow_header: bool) -> bool:
        """Parse a line of transaction file into the transaction object.

        Args:
            text_line (str): A text line of the file
            allow_header (bool): The method will append data to header when the formation
            of text line corresponds with one header field if allow_header is True, otherwise
            the method will always append the text to the actual content.

        Returns:
            bool: True for the text line satisfies one header field's formation,
            False for not satisfied.
        """
        if allow_header:
            if len(text_line) > 6 and text_line.startswith("From: "):
                re_match = regex.compile(r"From: <(.+)>").match(text_line)
                if re_match is not None:
                    self.sender = re_match.captures(1)[0]
                    return True
                else:
                    raise SyntaxError
            elif len(text_line) > 4 and text_line.startswith("To: "):
                re_match = regex.compile(r"To: (<(.+)>(,<(.+)>)*)").match(text_line)
                if re_match is not None:
                    recipients_str = re_match.captures(1)[0]
                    self.recipients = [r[1:-1] for r in recipients_str.split(",")]
                    return True
                else:
                    raise SyntaxError
            elif len(text_line) > 6 and text_line.startswith("Date: "):
                rfc5322 = text_line[6:]
                self.set_created_time(rfc5322)
                return True
            elif len(text_line) > 8 and text_line.startswith("Subject: "):
                re_match = regex.compile(r"Subject: (.+)").match(text_line)
                if re_match is not None:
                    self.subject = re_match.captures(1)[0]
                    return True
                else:
                    raise SyntaxError
        self.content.append(text_line)
        return False   # when content entry is started, header info is no longer accepted

    @classmethod
    def read_text(cls, text: str) -> "Transaction":
        """Parse email transaction file data into an Transaction object

        Args:
            text (str): the whole content of an email transaction file.

        Returns:
            Transaction: The parsed transaction object
        """
        text_lines = text.splitlines()
        new_txn = cls()
        allow_header: bool = True
        for content in text_lines:
            allow_header = new_txn.add_entry(content, allow_header)
        return new_txn

    def save_as(self, save_folder: str, file_prefix: str = ""):
        """Save the current transaction object as a file.

        Args:
            save_folder (str): The directory to save the file. Usually it is the inbox path.
            file_prefix (str, optional): The prefix of the filename. Defaults to "".
        """
        has_time = hasattr(self, "created_time_rfc5322") and hasattr(self, "created_time")
        if has_time:
            file_name = file_prefix + str(int(time.mktime(self.created_time.timetuple()))) + ".txt"
        else:
            file_name = file_prefix + "unknown.txt"
        inbox_file = open(str(Path(save_folder) / file_name), mode="w", encoding="ascii")
        print(f"From: <{self.sender}>", file=inbox_file)
        print(f"To: <{','.join(self.recipients)}>", file=inbox_file)
        if has_time:
            print(f"Date: {self.created_time_rfc5322}", file=inbox_file)
        if hasattr(self, "subject"):
            print(f"Subject: {self.subject}", file=inbox_file)
        for content_line in self.content:
            print(content_line.strip("\r\n"), file=inbox_file)
        inbox_file.close()
