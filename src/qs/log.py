import logging


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


logging.basicConfig(
    format=f"%(asctime)-15s %(levelname)s {Colors.OKBLUE}%(name)s{Colors.ENDC}: %(message)s"
)
root_logger = logging.getLogger()
root_logger.setLevel("INFO")
