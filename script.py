import sys
import os
import yaml
import requests
from datetime import datetime, timedelta
import logging
import threading
import signal
import queue
import time
from urllib.parse import urlparse
from collections import defaultdict

TIMER = 15

log_file_path = 'output.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # This will print only the log message, without any prefixes
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

health = defaultdict(lambda: (0, 0))

class HTTP_Endpoint:
    def __init__(self, name, url ,method, headers, body) -> None:
        if not name:
            raise ValueError("Name is required.")
        if not url:
            raise ValueError("Url is required")
        
        self.name = name
        self.url = url
        self.fqdn = urlparse(self.url).netloc
        self.method = method
        self.headers = headers
        self.body = body

        # Health tracking attributes
        self.status = 'UP'

    def __str__(self):
        return f"HTTPEndpoint(name={self.name}, url={self.url}, method={self.method})"

    def good_health(self):
        total , success = health[self.fqdn]
        health[self.fqdn] = (total+1, success+1)
        self.status = 'UP'

    def bad_health(self):
        total , success = health[self.fqdn]
        health[self.fqdn] = (total+1, success)
        self.status = 'DOWN'

    def get_availability(self):
        total, up = health[self.fqdn]
        return int(100 * (up / total)) if total > 0 else 0

    def hit_endpoint(self):
        start_time = datetime.now()
        response = None

        try:
            if self.method == 'GET':
                response = requests.get(self.url, headers=self.headers)
            elif self.method == 'POST':
                response = requests.post(self.url, headers=self.headers, json=self.body)
            elif self.method == 'PUT':
                response = requests.put(self.url, headers=self.headers, json=self.body)
            elif self.method == 'DELETE':
                response = requests.delete(self.url, headers=self.headers, json=self.body)

            latency = (datetime.now() - start_time).total_seconds() * 1000
            if 200 <= response.status_code < 300 and latency < 500:
                self.good_health()
            else:
                self.bad_health()
        except:
            self.bad_health()
        logger.info(f"{urlparse(self.url).netloc} has {self.get_availability()}% availability")


# Global variables
shutdown_flag = False
endpoint_queue = queue.Queue()

def signal_handler(sig, frame):
    global shutdown_flag
    logger.info("Received shutdown signal. Gracefully shutting down ...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def fetch_endpoints(file_name):
    # Load the endpoints from the YAML file and add them to the queue
    data = yaml.safe_load(open(file_name).read())
    for d in data:
        endpoint = HTTP_Endpoint(
            name=d.get('name', None),
            url=d.get('url', None),
            method=d.get('method', 'GET'),
            headers=d.get('headers', {}),
            body=d.get('body', None),
        )
        endpoint_queue.put(endpoint)

def health_check(endpoint: HTTP_Endpoint, duration: int):
    end_time = datetime.now() + timedelta(seconds=duration)
    while datetime.now() < end_time and not shutdown_flag:
        # hit_endpoint(endpoint)
        endpoint.hit_endpoint()
        time.sleep(TIMER)


def monitor_endpoints():
    while not shutdown_flag:
        if endpoint_queue.empty():
            logger.info("No more endpoints to process. Exiting loop.")
            break
        
        for _ in range(endpoint_queue.qsize()):
            endpoint = endpoint_queue.get()
            thread = threading.Thread(target=health_check, args=(endpoint, TIMER))
            thread.start()
            endpoint_queue.put(endpoint)

        logger.info("---------------------------")
        time.sleep(TIMER)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        fetch_endpoints(log_file)

        try:
            monitor_endpoints()
        except Exception as e:
            logger.error(f"Error occurred: {e}")
    logger.info("Program terminated.")
