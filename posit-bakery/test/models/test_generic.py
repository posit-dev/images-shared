import unittest

from tomlkit import TOMLDocument

from posit_bakery.models.generic import GenericTOMLModel


def test_generic_toml_model_load_toml_file_data(toml_basic_file):
    data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
    assert isinstance(data, TOMLDocument)
    assert data["name"] == "basic"
    assert data["section"]["key"] == "value"


def test_generic_toml_model_dump(toml_basic_file):
    data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
    model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
    model.document["name"] = "changed"
    model.dump()
    assert toml_basic_file.read_text() == model.dumps()


def test_generic_toml_model_dumps(toml_basic_file):
    expected = """name = "changed"

[section]
key = "value"
"""
    data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
    model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
    model.document["name"] = "changed"
    assert model.dumps() == expected
