import abc
import logging
import os
from pathlib import Path
from typing import List, Union

import tomlkit
from pydantic import BaseModel, ConfigDict


class GenericTOMLModel(BaseModel, abc.ABC):
    """Base class for TOML Document models

    :param filepath: Path to the TOML file represented by the model
    :param context: Path to the context (parent directory) of the TOML file
    :param document: tomlkit.TOMLDocument object
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    filepath: Path
    context: Path
    document: tomlkit.TOMLDocument
    model: BaseModel | None = None

    @staticmethod
    def read(filepath: Union[str, bytes, os.PathLike]) -> tomlkit.TOMLDocument:
        """Load a TOML file at the given filepath into a TOMLDocument object

        :param filepath: Path to the TOML file
        """
        with open(filepath, "rb") as f:
            return tomlkit.load(f)

    def dump(self, filepath: Union[str, bytes, os.PathLike] = None) -> None:
        """Write the TOMLDocument object to a file

        :param filepath: Path to write the TOML file to (defaults to self.filepath)
        """
        if filepath is None:
            filepath = self.filepath
        filepath = Path(filepath)
        logging.debug(f"Writing TOMLDocument to {filepath}")
        with open(filepath, "w") as f:
            tomlkit.dump(self.document, f)

    def dumps(self) -> str:
        """Return the TOMLDocument object as a string representation"""
        return tomlkit.dumps(self.document)

    @staticmethod
    def _pop_table_comments(item: tomlkit.items.Table) -> List:
        """Pop the trailing comment from a Table item

        This only supports one level of nested tables at the moment

        Return the comment and remove it from the Table
        """
        last_key = list(item.keys())[-1]
        body = item.get(last_key).value.body

        # Get the
        idx = None
        for i in range(len(body)):
            k, v = body[i]
            # Track the index when we find a comment/whitespace
            if idx is None:
                if isinstance(v, tomlkit.items.Comment) or isinstance(v, tomlkit.items.Whitespace):
                    idx = i
                    continue
            else:
                if not (isinstance(v, tomlkit.items.Comment) or isinstance(v, tomlkit.items.Whitespace)):
                    idx = None
                    continue

        comments = []
        # Collect the comments in reverse order
        if idx is not None:
            for i in range(len(body), idx, -1):
                comments.append(body.pop())
            comments.reverse()

        return comments

    @staticmethod
    def _append_table_comments(item: tomlkit.items.Table, comments: List) -> None:
        last_key = list(item.keys())[-1]
        body = item.get(last_key).value.body
        body.extend(comments)

    def update_table_item(self, table: str, key: str, value: any) -> tomlkit.TOMLDocument:
        """Update an element in the TOMLDocument object

        :param key: Key to update in the document
        :param value: Value to update the key with

        :return: Updated TOMLDocument
        """
        document = self.document
        item = document[table]
        assert isinstance(item, tomlkit.items.Table)

        comments = self._pop_table_comments(item)
        item[key] = value
        self._append_table_comments(item, comments)

        return document
