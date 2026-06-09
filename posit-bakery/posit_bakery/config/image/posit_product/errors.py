class DispatchVersionMismatchError(Exception):
    """Raised when a dispatched version override does not match the upstream manifest.

    Must NOT subclass ValueError or RequestException so it escapes the per-OS
    catch in _resolve_os_urls and the skip-on-error catch in load_dev_versions.
    """
