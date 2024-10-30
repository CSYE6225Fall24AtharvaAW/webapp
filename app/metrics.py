# metrics.py
from statsd import StatsClient

# Initialize StatsD client
statsd_client = StatsClient(host='localhost', port=8125, prefix='fastapi_app')
