""" LRIS2 daemon base class """
from libby.daemon import LibbyDaemon


class Lris2Daemon(LibbyDaemon):
    """Instantiates the LRIS2 daemon base using LibbyDaemon.

    Transport is rabbitmq and discovery is false since rabbitmq includes
    its own discovery.
    """
    transport = "rabbitmq"
    discovery_enabled = False