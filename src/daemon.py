""" LRIS2 daemon base class """
import os
from urllib.parse import quote

from libby.daemon import LibbyDaemon

# The instrument broker. Its credentials stay out of git: set these in
# /etc/lris2/secrets.env. A host other than the broker's names it in LRIS2_BROKER_HOST.
BROKER_HOST = "localhost"
BROKER_HOST_ENV = "LRIS2_BROKER_HOST"
BROKER_USER_ENV = "LRIS2_RABBITMQ_USER"
BROKER_PASSWORD_ENV = "LRIS2_RABBITMQ_PASSWORD"


def broker_url() -> str:
    """Return the instrument broker URL, with credentials from the environment."""
    user = os.environ.get(BROKER_USER_ENV)
    password = os.environ.get(BROKER_PASSWORD_ENV)
    host = os.environ.get(BROKER_HOST_ENV) or BROKER_HOST
    if not (user and password):
        return f"amqp://{host}"
    # quote() so a password containing @ or / cannot break the URL apart
    return f"amqp://{quote(user, safe='')}:{quote(password, safe='')}@{host}"


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
