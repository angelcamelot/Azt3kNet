"""Bootstrap DNS records for Azt3kNet managed domains.

This module is executed inside the ``azt3knet-dns-bootstrap`` container after
the Mailcow stack is healthy. Its responsibilities include:

* Creating initial A/MX/SPF/DMARC records in deSEC.
* Publishing DKIM keys fetched from Mailcow.
* Scheduling the recurring dynamic DNS update job.

The real implementation will be provided in a follow-up commit.
"""

from __future__ import annotations

from typing import NoReturn


def main() -> NoReturn:
    """Placeholder entry point until the automation is implemented."""

    raise NotImplementedError("dns_bootstrap main pending implementation")


if __name__ == "__main__":
    main()
