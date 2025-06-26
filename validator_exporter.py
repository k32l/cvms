#!/usr/bin/env python3
"""
Custom Dognet Validator Exporter
Complements CVMS by providing validator metrics that CVMS can't collect due to API limitations
"""

import requests
import time
from prometheus_client import start_http_server, Gauge, Info
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Prometheus metrics
validator_voting_power = Gauge('dognet_validator_voting_power', 'Validator voting power', ['validator_address', 'validator_index'])
validator_online = Gauge('dognet_validator_online', 'Validator online status (1=online, 0=offline)', ['validator_address'])
total_validators = Gauge('dognet_total_validators', 'Total number of validators')
total_voting_power = Gauge('dognet_total_voting_power', 'Total voting power in network')
validator_info = Info('dognet_validator', 'Validator information', ['validator_address'])

# Configuration
RPC_ENDPOINT = "https://rpc-internal.dognet.mitosis.org/cc/rpc"
SCRAPE_INTERVAL = 30  # seconds
EXPORTER_PORT = 9201  # Different from CVMS ports (9200/9300)

def get_validators():
    """Fetch current validator set from RPC"""
    try:
        response = requests.get(f"{RPC_ENDPOINT}/validators", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'result' in data and 'validators' in data.get('result', {}):
            return data['result']
        else:
            logger.error(f"Unexpected response format: {data}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to fetch validators: {e}")
        return None

def get_consensus_state():
    """Get current consensus state to check which validators are active"""
    try:
        response = requests.get(f"{RPC_ENDPOINT}/consensus_state", timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('result', {})
    except Exception as e:
        logger.warning(f"Failed to fetch consensus state: {e}")
        return {}

def update_metrics():
    """Update Prometheus metrics with current validator data"""
    validators_data = get_validators()
    if not validators_data:
        return
    
    validators = validators_data.get('validators', [])
    block_height = validators_data.get('block_height', 0)
    
    logger.info(f"Found {len(validators)} validators at block {block_height}")
    
    # Reset metrics
    validator_voting_power.clear()
    validator_online.clear()
    validator_info.clear()
    
    total_power = 0
    
    for i, validator in enumerate(validators):
        address = validator.get('address', '')
        voting_power = int(validator.get('voting_power', 0))
        pub_key = validator.get('pub_key', {})
        
        # Update metrics
        validator_voting_power.labels(
            validator_address=address,
            validator_index=str(i)
        ).set(voting_power)
        
        # Assume validator is online if they have voting power > 0
        validator_online.labels(validator_address=address).set(1 if voting_power > 0 else 0)
        
        # Store validator info
        validator_info.labels(validator_address=address).info({
            'pub_key_type': pub_key.get('type', ''),
            'pub_key_value': pub_key.get('value', '')[:20] + '...',  # Truncate for readability
            'voting_power': str(voting_power),
            'validator_index': str(i)
        })
        
        total_power += voting_power
    
    # Update totals
    total_validators.set(len(validators))
    total_voting_power.set(total_power)
    
    logger.info(f"Updated metrics: {len(validators)} validators, {total_power:,} total voting power")

def main():
    """Main exporter loop"""
    logger.info(f"Starting Dognet Validator Exporter on port {EXPORTER_PORT}")
    logger.info(f"RPC endpoint: {RPC_ENDPOINT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics server started on http://localhost:{EXPORTER_PORT}/metrics")
    
    while True:
        try:
            update_metrics()
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
        
        time.sleep(SCRAPE_INTERVAL)

if __name__ == "__main__":
    main() 