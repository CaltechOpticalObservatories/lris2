""" LRIS2 daemon base class """
import os

from libby.daemon import LibbyDaemon

# The instrument broker. A daemon on another host names it in LRIS2_BROKER_HOST;
# the broker lets the guest account in remotely (loopback_users = none)
BROKER_HOST = "localhost"
BROKER_HOST_ENV = "LRIS2_BROKER_HOST"


def broker_url() -> str:
    """Return the instrument broker URL."""
    return f"amqp://{os.environ.get(BROKER_HOST_ENV) or BROKER_HOST}"


class Lris2Daemon(LibbyDaemon):
    """Instantiates the LRIS2 daemon base using LibbyDaemon.

    Transport is rabbitmq and discovery is false since rabbitmq includes
    its own discovery.
    """
    transport = "rabbitmq"
    discovery_enabled = False

    def config_rabbitmq_url(self) -> str:
        """Return the configured URL if there is one, else the instrument broker."""
        return self.rabbitmq_url or broker_url()
