# Distributed Endpoint API Router

A resilient Python routing API designed to handle high availability and load balancing by dynamically directing traffic to live mirrored endpoints.

## Architecture Highlights
- **Health Checks & Monitoring**: Continuously pings downstream nodes to ensure only live, healthy servers receive active traffic.
- **Dynamic Failover**: Instantly reroutes API payloads to backup mirrors if a primary node goes offline or times out.
- **Tech Stack**: Python, Load Balancing algorithms, REST API architecture.

## Setup
```bash
pip install -r requirements.txt
python router.py --config mirrors.json
```


<!-- activity-sync: 2026-08-28 -->
