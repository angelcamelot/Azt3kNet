"""Service layer integrations for external infrastructure."""

from .dns_manager import DeSECDNSManager, RRSet
from .mailcow_provisioner import MailcowProvisioner, MailboxCredentials
from .mail_service import AgentMailbox, MailService

__all__ = [
    "AgentMailbox",
    "DeSECDNSManager",
    "MailboxCredentials",
    "MailService",
    "MailcowProvisioner",
    "RRSet",
]
