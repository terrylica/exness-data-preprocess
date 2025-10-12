"""Basic tests to ensure package can be imported and has correct metadata."""

import exness_data_preprocess as edp


def test_package_import():
    """Test that package can be imported."""
    assert edp.__name__ == "exness_data_preprocess"


def test_version_exists():
    """Test that package has version attribute."""
    assert hasattr(edp, "__version__")
    assert isinstance(edp.__version__, str)


def test_processor_class_exists():
    """Test that ExnessDataProcessor class exists."""
    assert hasattr(edp, "ExnessDataProcessor")
    assert callable(edp.ExnessDataProcessor)


def test_processor_instantiation():
    """Test that ExnessDataProcessor can be instantiated."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        processor = edp.ExnessDataProcessor(base_dir=Path(tmpdir))
        assert processor is not None
        assert processor.base_dir == Path(tmpdir)
