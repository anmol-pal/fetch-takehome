import sys
import os
import yaml
import requests
from datetime import datetime
import logging
import threading
import signal
import queue
import time
from urllib.parse import urlparse
from collections import defaultdict

# Global variables
shutdown_flag = False
endpoint_queue = queue.Queue()
health = defaultdict(lambda: (0, 0))
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

class HTTP_Endpoint:
    def __init__(self, name, url, method, headers, body) -> None:
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
        total, success = health[self.fqdn]
        health[self.fqdn] = (total + 1, success + 1)
        self.status = 'UP'

    def bad_health(self):
        total, success = health[self.fqdn]
        health[self.fqdn] = (total + 1, success)
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




def signal_handler(sig, frame):
    global shutdown_flag
    logger.info("Received shutdown signal. Gracefully shutting down ...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log_health():
    if health:
        for fqdn, (total, success) in health.items():
            avail = int(100 * (success / total)) if total > 0 else 0
            logger.info(f"{fqdn} has {avail}% availability")
        logger.info("---------------------------")

def fetch_endpoints(file_name):
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

def health_check(endpoint: HTTP_Endpoint):
    endpoint.hit_endpoint()

def monitor_endpoints():
    while not shutdown_flag:
        if endpoint_queue.empty():
            logger.info("No more endpoints to process. Waiting for new endpoints...")
            time.sleep(15)  # Control the main loop timing
            continue
        
        for _ in range(endpoint_queue.qsize()):
            endpoint = endpoint_queue.get()
            thread = threading.Thread(target=health_check, args=(endpoint,))
            thread.start()
            thread.join()
            endpoint_queue.put(endpoint)

        log_health()

        time.sleep(15)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        fetch_endpoints(log_file)

        try:
            monitor_endpoints()
        except Exception as e:
            logger.error(f"Error occurred: {e}")
    logger.info("Program terminated.")
