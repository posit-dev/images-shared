import abc
from typing import Any, List, Dict

from posit_bakery.util import cached_session


class AbstractResolver(abc.ABC):
    """ABC for resolvers, a general term for classes that take input data (usually a dict or str) and return a value."""

    def __init__(self):
        self.metadata = {}

    def set_metadata(self, metadata: Dict):
        """Provided as a general input for providing global data. Used in formatting strings."""
        self.metadata = metadata

    @abc.abstractmethod
    def format(self):
        """Method used to format given data before resolution of a value."""
        pass

    @abc.abstractmethod
    def resolve(self, data: Any) -> Any:
        """Method used to resolve a value from the given data.

        :param data: The data to resolve a value from.
        :return: The resolved value.
        """
        pass


class TextResolver(AbstractResolver):
    """Resolver for cases where no transformation is needed."""

    def __init__(self):
        super().__init__()

    def format(self):
        """No formatting needed or performed."""
        return

    def resolve(self, data: str) -> str:
        """Return the given data as is.

        :param data: The data to return.
        :return: The given data.
        """
        return data.strip()


class StringMapPathResolver(AbstractResolver):
    """Resolver for cases where the target value is in a string keyed dictionary."""

    def __init__(self, key_path: List[str]):
        super().__init__()
        self.key_path = key_path
        self._formatted_key_path = None  # Preserves the original key path if we reuse the resolver

    def format(self):
        self._formatted_key_path = [element.format(**self.metadata) for element in self.key_path]

    def resolve(self, data: Dict[str, Any]) -> Dict[Any, Any] | Any | None:
        """Resolve the valuea at the given path from the given dictionary.

        :param data: The dictionary to resolve the value from. All levels in the key path are expected to be
                     dictionaries using string keys.
        :return: The resolved value. None if the path does not exist.
        """
        self.format()
        for key in self._formatted_key_path:
            data = data.get(key)
            if data is None:
                break
        return data


class ArrayPropertyResolver(AbstractResolver):
    """Resolver for cases where the target value is in a list of dictionaries and should be resolved by property
    matching.
    """

    def __init__(self, prop: str, value: str):
        """Create a new ArrayPropertyResolver.

        :param prop: The property to match on. Expected to appear in every dictionary in list. Will be formatted using
                     metadata.
        :param value: The value to match the property to. Will be formatted using metadata.
        """
        super().__init__()
        self.prop = prop
        self._formatted_prop = None  # Preserves the original prop if we reuse the resolver
        self.value = value
        self._formatted_value = None  # Preserves the original value if we reuse the resolver

    def format(self):
        """Format the prop and value strings using metadata."""
        self._formatted_prop = self.prop.format(**self.metadata)
        self._formatted_value = self.value.format(**self.metadata)

    def resolve(self, data: list[dict]) -> Any | None:
        """Resolve the matching dictionary from the given list of dictionaries.

        :param data: The list of dictionaries to search through.
        :return: The dictionary that matches the given property and value. None if no match is found.
        """
        self.format()
        for item in data:
            if item.get(self._formatted_prop) == self._formatted_value:
                return item
        return None


class ReleaseBranchResolver(AbstractResolver):
    """Resolver that selects a release entry from a list by the ``release_branch`` metadata value."""

    def format(self):
        return

    def resolve(self, data: list[dict]) -> dict | None:
        """Resolve the entry for the release branch.

        :param data: The list of release entries. Each is expected to have "branch" and "version" properties.
        :return: The first entry for "latest", otherwise the entry whose branch or version equals the release branch.
                 None if there is no match.
        """
        release_branch = self.metadata["release_branch"]
        if release_branch == "latest":
            return data[0] if data else None
        for item in data:
            if release_branch in (item.get("branch"), item.get("version")):
                return item
        return None


class UrlFetchResolver(AbstractResolver):
    """Resolver for cases where the given data is a URL to a JSON document that holds the target value."""

    def format(self):
        return

    def resolve(self, data: str) -> Any:
        """Fetch the JSON document at the given URL.

        :param data: The URL to fetch.
        :return: The decoded JSON document.
        """
        response = cached_session().get(data)
        response.raise_for_status()
        return response.json()


class ChainedResolver(AbstractResolver):
    """Meta resolver that chains multiple resolvers together."""

    def __init__(self, resolvers: List[AbstractResolver]):
        """Create a new ChainedResolver.

        :param resolvers: The resolvers to chain together. Resolvers are executed in the order given and pass their
                          output to the next resolver.
        """
        super().__init__()
        self.resolvers = resolvers

    def format(self):
        """Each resolver is expected to perform their own formatting."""
        return

    def resolve(self, data: Dict[Any, Any]) -> Dict[Any, Any] | Any | None:
        """Resolve the given data by passing it through each resolver in order.

        :param data: The data object to execute resolvers against.
        :return: The resolved data. Stops execution and returns None if any resolver in the chain returns None.
        """
        for resolver in self.resolvers:
            resolver.set_metadata(self.metadata)
            data = resolver.resolve(data)
            if data is None:
                break
        return data
