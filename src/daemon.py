""" LRIS2 daemon base class """
from libby.config_resolve import resolve_rabbitmq_url
from libby.daemon import LibbyDaemon


class Lris2Daemon(LibbyDaemon):
    """Instantiates the LRIS2 daemon base using LibbyDaemon.

    Transport is rabbitmq and discovery is false since rabbitmq includes
    its own discovery.
    """
    transport = "rabbitmq"
    discovery_enabled = False

    def config_rabbitmq_url(self) -> str:
        """Return the broker from LIBBY_RABBITMQ_URL, else the daemon config, else localhost."""
        return str(resolve_rabbitmq_url(None, {"rabbitmq_url": self.rabbitmq_url}))
