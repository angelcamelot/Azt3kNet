"""Service layer integrations for external infrastructure."""

from .dns_manager import DeSECDNSManager, RRSet
from .mailcow_provisioner import MailcowProvisioner, MailboxCredentials
from .mail_service import AgentMailbox, MailService
from .resilient_http_client import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ClientMetrics,
    ResilientHTTPClient,
    RetryConfiguration,
)

__all__ = [
    "AgentMailbox",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "DeSECDNSManager",
    "ClientMetrics",
    "MailboxCredentials",
    "MailService",
    "MailcowProvisioner",
    "ResilientHTTPClient",
    "RRSet",
    "RetryConfiguration",
]
