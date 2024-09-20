import sys, os
import yaml
import requests
from datetime import datetime
import logging

TIMER = 15


# Configure the logger
log_file_path = 'output.log'
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(levelname)s - %(message)s',
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
        self.method = method
        self.headers = headers
        self.body = body

    def __str__(self):
        return f"HTTPEndpoint(name={self.name}, url={self.url}, method={self.method}, headers={self.headers}, body={self.body})"
    
    def as_dict(self):
        return {
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "body": self.body
        }

class Health:
    def __init__(self, endpoint: HTTP_Endpoint):
        self.endpoint = endpoint
        self.total_requests = 0  # Count of total requests made
        self.up_count = 0  # Count of times the endpoint was up
        self.status = 'UP'

    def good_health(self):
        self.total_requests +=1
        self.up_count += 1
        self.status = 'UP'

    def bad_health(self):
        self.total_requests +=1
        self.up_count -= 1
        self.status = 'DOWN'

    def get_availability(self):
        return int(100 * (self.up_count / self.total_requests))
    

def fetch_endpoint(file_name):
    data = yaml.safe_load(open(file_name).read())
    for d in data:
        endpoint = HTTP_Endpoint(
            name = d.get('name',None),
            url = d.get('url', None),
            method=d.get('method','GET'),
            headers = d.get('headers') if d.get('headers') and len(d.get('headers')) > 0 else {},
            body = d.get('body') if d.get('body') else {},
        )
        health = health_check(endpoint, TIMER)
        logger.info(endpoint)
        print(endpoint)

def health_check(endpoint: HTTP_Endpoint, delay_in_seconds: int):
    def job():
        print(delay_in_seconds)
        # if date



def hit_endpoint(endpoint: HTTP_Endpoint, health: Health):
    latency = None
    start_time = datetime.now()
    response = None

    try:
        if endpoint.method == 'GET':
            response = requests.get(endpoint.url, headers=endpoint.headers)
        elif endpoint.method == 'POST':
            response = requests.post(endpoint.url, headers=endpoint.headers, json=endpoint.body)
        elif endpoint.method == 'PUT':
            response = requests.put(endpoint.url, headers=endpoint.headers, json=endpoint.body)
        elif endpoint.method == 'DELETE':
            response = requests.delete(endpoint.url, headers=endpoint.headers, json=endpoint.body)
        end_time = datetime.now()

    except requests.exceptions.RequestException as e:
        pass
    
    latency = (end_time - start_time).total_seconds() * 1000
    if response:
        if 200 <= response.status_code < 300 and latency < 500 :
            health.good_health()
    else:
        health.bad_health()
    log_information = f"{endpoint.url} has {health.get_availability()} availability percentage"
    logger.info(log_information)







log_file = None
if len(sys.argv) > 1:
    log_file = sys.argv[1]
    fetch_endpoint(log_file)