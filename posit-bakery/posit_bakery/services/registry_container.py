import logging

import python_on_whales

log = logging.getLogger(__name__)


class RegistryContainer:
    def __init__(self, image: str = "docker.io/registry:3", port: int = 5000, restart_policy: str = "always"):
        log.debug(f"Starting registry container at port {port}...")
        self._port = port
        self._container = python_on_whales.docker.run(
            image=image,
            publish=[(port, 5000)],
            restart=restart_policy,
        )
        log.debug("Started registry container.")

    def url(self):
        """Get the URL of the registry."""
        return f"localhost:{self._port}"

    def status(self):
        """Get the status of the registry container."""
        if not self._container.exists():
            return "not_found"
        return self._container.status

    def stop(self, timeout: int | None = None):
        """Stop the registry container."""
        self._container.stop(timeout=timeout)

    def remove(self, force: bool = False, volumes: bool = True):
        """Remove the registry container."""
        self._container.remove(force=force, volumes=volumes)

    def kill(self, signal: str | None = None):
        """Kill the registry container."""
        self._container.kill(signal=signal)

    def __enter__(self):
        return self._container

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._container.exists():
            log.debug("Registry container does not exist; nothing to clean up.")
            return

        log.debug(f"Stopping registry container {self._container.name}...")
        self.stop()
        log.debug(f"Stopped registry container {self._container.name}.")
        log.debug(f"Removing registry container {self._container.name} and data...")
        self.remove()
        log.debug("Removed registry container.")
