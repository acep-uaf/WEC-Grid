"""
Basic import tests for WEC-GRID core modules.
"""

import pytest


def test_pypsa():
    """Test PyPSA module can be imported."""
    import pypsa
    assert pypsa is not None
    
def test_wecgrid_database():
    """Test database module can be imported."""
    from wecgrid.util.database import WECGridDB
    assert WECGridDB is not None


def test_wecgrid_time():
    """Test WECGridTime can be imported."""
    from wecgrid.util.time import WECGridTime
    assert WECGridTime is not None


def test_wecgrid_plot():
    """Test plotting module can be imported."""
    from wecgrid.util.plot import WECGridPlot
    assert WECGridPlot is not None


def test_wecgrid_gridstate():
    """Test GridState can be imported."""
    from wecgrid.modelers.power_system.base import GridState
    assert GridState is not None


def test_wecgrid_engine():
    """Test Engine can be imported (may skip if external deps missing)."""
    try:
        from wecgrid.engine import Engine
        assert Engine is not None
    except ImportError as e:
        # Skip if external dependencies are missing
        if any(x in str(e).lower() for x in ["matlab", "psspy", "psse"]):
            pytest.skip(f"External dependency not available: {e}")
        else:
            raise
