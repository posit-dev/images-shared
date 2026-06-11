class DispatchVersionMismatchError(Exception):
    """Raised when a dispatched version override does not match the upstream manifest.

    Must NOT subclass ValueError or RequestException so it escapes the per-OS
    catch in _resolve_os_urls and the skip-on-error catch in load_dev_versions.
    """


class ArtifactNotAvailableError(Exception):
    """Raised when a HEAD probe on an overridden artifact URL returns a non-2xx status.

    Must NOT subclass ValueError or RequestException so it escapes the per-OS
    catch in _resolve_os_urls and propagates as a hard build failure.
    """


class VersionSubstitutionError(Exception):
    """Raised when the manifest version cannot be located in the manifest URL.

    Prevents silently shipping the wrong (un-substituted) artifact URL.
    Must NOT subclass ValueError or RequestException for the same reasons as
    ArtifactNotAvailableError.
    """
