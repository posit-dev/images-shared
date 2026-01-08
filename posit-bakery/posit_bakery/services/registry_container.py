import logging

import python_on_whales

log = logging.getLogger(__name__)


class RegistryContainer:
    _CONTAINER_PORT = 5000

    def __init__(self, image: str = "docker.io/registry:3", port: int | None = None, restart_policy: str = "always"):
        log.debug(f"Starting registry container at port {port}...")
        self._container = python_on_whales.docker.run(
            image=image,
            publish=[(port, self._CONTAINER_PORT)] if port is not None else [(self._CONTAINER_PORT,)],
            restart=restart_policy,
            detach=True,
        )
        log.debug("Started registry container.")

    @property
    def url(self):
        """Get the URL of the registry."""
        if not self._container.exists():
            raise RuntimeError("Registry container does not exist.")

        port_map = self._container.network_settings.ports.get(f"{self._CONTAINER_PORT}/tcp")
        if not port_map:
            raise RuntimeError("Registry container port is not mapped.")
        mapped_port = port_map[0]["HostPort"]

        return f"localhost:{mapped_port}"

    @property
    def status(self):
        """Get the status of the registry container."""
        if not self._container.exists():
            return "not_found"
        return self._container.state.status

    def stop(self, timeout: int | None = None):
        """Stop the registry container."""
        self._container.stop(time=timeout)

    def remove(self, force: bool = False, volumes: bool = True):
        """Remove the registry container."""
        self._container.remove(force=force, volumes=volumes)

    def kill(self, signal: str | None = None):
        """Kill the registry container."""
        self._container.kill(signal=signal)

    def __enter__(self):
        return self

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
