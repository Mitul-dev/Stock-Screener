import pytest
import os

def test_dashboard_import():
    try:
        from equity_engine.dashboard.app import main
        assert True
    except ImportError:
        pytest.fail("Failed to import Streamlit app")
