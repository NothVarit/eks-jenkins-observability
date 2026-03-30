import logging
from datetime import datetime, timezone

from kubernetes import client
from prometheus_client.core import GaugeMetricFamily

logger = logging.getLogger(__name__)


class PodCollector:
    def __init__(self, core_v1: client.CoreV1Api, custom_api: client.CustomObjectsApi):
        self.core_v1    = core_v1
        self.custom_api = custom_api

    def describe(self):
        yield GaugeMetricFamily("pod_availability_ratio", "1 if Ready, 0 if not")
        yield GaugeMetricFamily("pod_restart_total",      "Total container restarts")
        yield GaugeMetricFamily("pod_unhealthy",          "1 if not Ready or Failed")
        yield GaugeMetricFamily("pod_pending",            "1 if phase is Pending")
        yield GaugeMetricFamily("pod_age_seconds",        "Seconds since pod started")

    def collect(self):
        availability = GaugeMetricFamily(
            "pod_availability_ratio",
            "1 if the pod is Ready, 0 if not Ready",
            labels=["namespace", "pod"],
        )
        restarts = GaugeMetricFamily(
            "pod_restart_total",
            "Total number of container restarts for the pod",
            labels=["namespace", "pod"],
        )
        unhealthy = GaugeMetricFamily(
            "pod_unhealthy",
            "1 if the pod is not Ready or in Failed state, 0 otherwise",
            labels=["namespace", "pod"],
        )
        pending = GaugeMetricFamily(
            "pod_pending",
            "1 if the pod is in Pending phase, 0 otherwise",
            labels=["namespace", "pod"],
        )
        age = GaugeMetricFamily(
            "pod_age_seconds",
            "Number of seconds since the pod started",
            labels=["namespace", "pod"],
        )

        self._collect_core_metrics(availability, restarts, unhealthy, pending, age)

        yield availability
        yield restarts
        yield unhealthy
        yield pending
        yield age

    def _collect_core_metrics(self, availability, restarts, unhealthy, pending, age):
        try:
            pods = self.core_v1.list_pod_for_all_namespaces(watch=False)
        except Exception as e:
            logger.error(f"Failed to list pods from core API: {e}")
            return

        now = datetime.now(timezone.utc)

        for pod in pods.items:
            ns   = pod.metadata.namespace
            name = pod.metadata.name
            ready = self._is_pod_ready(pod)

            availability.add_metric([ns, name], 1.0 if ready else 0.0)

            is_unhealthy = not ready or pod.status.phase == "Failed"
            unhealthy.add_metric([ns, name], 1.0 if is_unhealthy else 0.0)

            is_pending = pod.status.phase == "Pending"
            pending.add_metric([ns, name], 1.0 if is_pending else 0.0)

            total_restarts = 0
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    total_restarts += cs.restart_count
            restarts.add_metric([ns, name], float(total_restarts))

            pod_age = 0.0
            if pod.status.start_time:
                pod_age = (now - pod.status.start_time).total_seconds()
            age.add_metric([ns, name], pod_age)

    def _is_pod_ready(self, pod) -> bool:
        if not pod.status.conditions:
            return False
        return any(
            c.type == "Ready" and c.status == "True"
            for c in pod.status.conditions
        )