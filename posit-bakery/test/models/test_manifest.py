from posit_bakery.models import manifest


class TestGossConfig:
    def test_goss_config(self, basic_manifest_obj):
        """Test creating a basic GossConfig object does not raise an exception"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )

    def test_default_deps(self, basic_manifest_obj):
        """Test the default deps path generation for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )
        assert goss_config.deps == version_context / "deps"

    def test_default_test_path(self, basic_manifest_obj):
        """Test the default test path generation for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )
        assert goss_config.test_path == version_context / "test"

    def test_deps_render(self, basic_context, basic_manifest_obj):
        """Test the deps path generation with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
            deps=basic_context / "{{ image_name }}" / "deps" / "{{ build.version }}",
        )
        assert goss_config.deps == basic_context / "test-image" / "deps" / "1.0.0"

    def test_test_path_render(self, basic_context, basic_manifest_obj):
        """Test the test path generation with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
            test_path=basic_context / "{{ image_name }}" / "test" / "{{ target.type }}",
        )
        assert goss_config.test_path == basic_context / "test-image" / "test" / "min"

    def test_wait_render(self, basic_manifest_obj):
        """Test the wait value with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image", "goss_wait": 10},
            wait="{{ goss_wait }}",
        )
        assert goss_config.wait == 10

    def test_command_render(self, basic_manifest_obj):
        """Test the command value with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.manifest_context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image", "goss_command": "start_app"},
            command="{{ goss_command }}",
        )
        assert goss_config.command == "start_app"
