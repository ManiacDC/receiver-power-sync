"""main loop for EISCP TCP Relay"""

import logging
import sys
import threading
import time

from .config import get_config
from .constants import LOG_LEVEL
from .service import ReceiverSyncService


def init_logging():
    """initializes logging"""

    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s,%(msecs)d %(levelname)s/%(module)s] : %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL)

    return logger


def main_loop():
    """main loop for running the servers"""

    logger = init_logging()

    config = get_config()

    with ReceiverSyncService(logger, config) as eiscp_sync:

        listener_threads = []

        for listener in eiscp_sync.listeners:
            listener_thread = threading.Thread(target=listener.listen_forever)
            listener_thread.daemon = True
            listener_thread.start()
            listener_threads.append(listener_thread)

        count = 0

        while True:
            time.sleep(0.1)
            count += 1
            if count == 100:
                count = 0
                # ensure receivers are in sync once about every 10 seconds
                eiscp_sync.send_pwr_question_to_primary()
