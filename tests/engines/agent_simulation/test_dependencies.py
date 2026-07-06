"""Test that agent simulation dependencies are importable."""
import camel
import zep_cloud


def test_camel_ai_import():
    """Verify camel-ai (camel module) is importable."""
    import camel
    assert hasattr(camel, '__version__')


def test_zep_cloud_import():
    """Verify zep-cloud is importable."""
    import zep_cloud
    assert hasattr(zep_cloud, '__version__')