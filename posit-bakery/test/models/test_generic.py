from ruamel.yaml import CommentedMap

from posit_bakery.models.generic import GenericYAMLModel


class TestGenericYAMLModel:
    def test_generic_yaml_model_load_yaml_file_data(self, yaml_basic_file):
        """Test that the load_yaml_file_data method returns a YAMLDocument with expected data"""
        data = GenericYAMLModel.read(yaml_basic_file)
        assert isinstance(data, CommentedMap)
        assert data["name"] == "basic"
        assert data["section"]["key"] == "value"

    def test_generic_yaml_model_dump(self, yaml_basic_file):
        """Test that the dump method writes the expected data back to the file"""
        data = GenericYAMLModel.read(yaml_basic_file)
        model = GenericYAMLModel(filepath=yaml_basic_file, context=yaml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        model.dump()
        assert yaml_basic_file.read_text() == model.dumps()

    def test_generic_yaml_model_dumps(self, yaml_basic_file):
        """Test that the dumps method returns the expected YAML string"""
        expected = """name: "changed"

section:
  key: "value"
"""
        data = GenericYAMLModel.read(yaml_basic_file)
        model = GenericYAMLModel(filepath=yaml_basic_file, context=yaml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        assert model.dumps() == expected
