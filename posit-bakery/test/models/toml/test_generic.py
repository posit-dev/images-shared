import tomlkit
from pathlib import Path

from posit_bakery.models.toml.generic import GenericTOMLModel

from ..helpers import dedent_toml_str


class TestGenericTOMLModel:
    def test_generic_toml_model_load_toml_file_data(self, toml_basic_file):
        """Test that the load_toml_file_data method returns a TOMLDocument with expected data"""
        data = GenericTOMLModel.read(toml_basic_file)
        assert isinstance(data, tomlkit.TOMLDocument)
        assert data["name"] == "basic"
        assert data["section"]["key"] == "value"

    def test_generic_toml_model_dump(self, toml_basic_file):
        """Test that the dump method writes the expected data back to the file"""
        data = GenericTOMLModel.read(toml_basic_file)
        model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        model.dump()
        assert toml_basic_file.read_text() == model.dumps()

    def test_generic_toml_model_dumps(self, toml_basic_file):
        """Test that the dumps method returns the expected TOML string"""
        expected = dedent_toml_str("""
            name = "changed"

            [section]
            key = "value"
            """)

        data = GenericTOMLModel.read(toml_basic_file)
        model = GenericTOMLModel(filepath=toml_basic_file, context=toml_basic_file.parent, document=data)
        model.document["name"] = "changed"
        assert model.dumps() == expected


class GenericModel(GenericTOMLModel):
    filepath: Path = Path()
    context: Path = Path()


class TestGenericTOMLComments:
    """Test the ability to preserve comments in a TOML file

    We use examples of the config and manifest documents in these tests,
    but the update functionality is
    """

    def test_preserve_post_manifest_build(self):
        """Test that comments after the build section are preserved"""

        initial: str = dedent_toml_str("""
            # Start of the file

            # Define the builds
            [build."1.0.0"]
            os = ["linux"]
            latest = true

            # Define the targets
            # With a second line of comments
            [target.std]
            """)

        expected: str = dedent_toml_str("""
            # Start of the file

            # Define the builds
            [build."1.0.0"]
            os = ["linux"]
            latest = true

            [build."0.9.9"]
            os = ["linux"]

            # Define the targets
            # With a second line of comments
            [target.std]
            """)

        model: GenericTOMLModel = GenericModel(document=tomlkit.parse(initial))
        doc = model.update_table_item(table="build", key="0.9.9", value={"os": ["linux"]})

        assert tomlkit.dumps(doc) == expected
