"""Bootstrap de registros DNS para dominios de Azt3kNet.

Este módulo se ejecutará dentro del contenedor `azt3knet-dns-bootstrap` después de que
Mailcow esté operativo. Su responsabilidad incluye:

* Crear registros A/MX/SPF/DMARC iniciales en deSEC.
* Publicar claves DKIM recuperadas desde Mailcow.
* Programar/registrar el job de actualización dinámica.

La implementación real se añadirá en commits posteriores.
"""

from __future__ import annotations

from typing import NoReturn


def main() -> NoReturn:
    """Punto de entrada provisional.

    TODO: Implementar lógica de bootstrap DNS y orquestación con deSEC.
    """

    raise NotImplementedError("dns_bootstrap main pending implementation")


if __name__ == "__main__":
    main()
