"""Shared, lazily-initialized clients for the observability backends and
the Kubernetes API. Every tool module imports from here instead of
constructing its own client, so config (base URLs, timeouts, kubeconfig)
stays in one place.
"""

from __future__ import annotations

import functools

import httpx
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from config import settings


@functools.lru_cache(maxsize=1)
def http_client() -> httpx.Client:
    return httpx.Client(timeout=settings.request_timeout_seconds)


def _load_kube_config_once() -> None:
    if getattr(_load_kube_config_once, "_loaded", False):
        return
    try:
        if settings.kubeconfig_path:
            k8s_config.load_kube_config(config_file=settings.kubeconfig_path)
        else:
            k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    _load_kube_config_once._loaded = True


@functools.lru_cache(maxsize=1)
def core_v1() -> k8s_client.CoreV1Api:
    _load_kube_config_once()
    return k8s_client.CoreV1Api()


@functools.lru_cache(maxsize=1)
def apps_v1() -> k8s_client.AppsV1Api:
    _load_kube_config_once()
    return k8s_client.AppsV1Api()
