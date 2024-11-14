import unittest

from tomlkit import TOMLDocument

from posit_bakery.models.generic import GenericTOMLModel


class TestGenericTOMLModel:
    def test_generic_toml_model_load_toml_file_data(self, toml_basic_file):
        """Test that the load_toml_file_data method returns a TOMLDocument with expected data"""
        data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
        assert isinstance(data, TOMLDocument)
        assert data["name"] == "basic"
        assert data["section"]["key"] == "value"

    def test_generic_toml_model_dump(self, toml_basic_file):
        """Test that the dump method writes the expected data back to the file"""
        data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
        model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        model.dump()
        assert toml_basic_file.read_text() == model.dumps()

    def test_generic_toml_model_dumps(self, toml_basic_file):
        """Test that the dumps method returns the expected TOML string"""
        expected = """name = "changed"

[section]
key = "value"
"""
        data = GenericTOMLModel.load_toml_file_data(toml_basic_file)
        model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        assert model.dumps() == expected
