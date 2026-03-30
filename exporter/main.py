import logging
import os
import sys
import time

from kubernetes import client, config
from prometheus_client import REGISTRY, start_http_server
from prometheus_client.core import CollectorRegistry

from collector import PodCollector

# ── Logging setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_k8s_clients():
    """
    Builds Kubernetes API clients.

    - Inside cluster  → uses the ServiceAccount token mounted automatically
                        at /var/run/secrets/kubernetes.io/serviceaccount/
    - Outside cluster → falls back to ~/.kube/config (for local dev/testing)
    """
    try:
        config.load_incluster_config()
        logger.info("Using in-cluster Kubernetes config (ServiceAccount token)")
    except config.ConfigException:
        logger.warning("In-cluster config not found — falling back to kubeconfig")
        config.load_kube_config()

    core_v1    = client.CoreV1Api()
    custom_api = client.CustomObjectsApi()
    return core_v1, custom_api


def main():
    port = int(os.environ.get("EXPORTER_PORT", "8000"))
    scrape_interval = int(os.environ.get("SCRAPE_INTERVAL", "0"))
    # scrape_interval=0 means on-demand (Prometheus pulls /metrics)
    # scrape_interval>0 means pre-compute in a background loop (optional)

    # ── Build K8s clients ─────────────────────────────────────────────
    try:
        core_v1, custom_api = build_k8s_clients()
    except Exception as e:
        logger.error(f"Failed to initialize Kubernetes clients: {e}")
        sys.exit(1)

    # ── Register custom collector ─────────────────────────────────────
    # Use a fresh registry — avoids exposing default Go/Python runtime metrics
    registry = CollectorRegistry()
    collector = PodCollector(core_v1, custom_api)
    registry.register(collector)

    # ── Start HTTP server ─────────────────────────────────────────────
    start_http_server(port, registry=registry)
    logger.info(f"Pod exporter listening on :{port}")
    logger.info(f"Metrics : http://localhost:{port}/metrics")

    # Keep the process alive
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()