"""Service layer integrations for external infrastructure."""

from .dns_manager import DeSECDNSManager, RRSet
from .mailjet_provisioner import MailboxCredentials, MailjetProvisioner
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
    "MailjetProvisioner",
    "ResilientHTTPClient",
    "RRSet",
    "RetryConfiguration",
]
