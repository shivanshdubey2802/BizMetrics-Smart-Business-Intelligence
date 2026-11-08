import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

os.environ["LOKY_MAX_CPU_COUNT"] = "4"

PAGES = sorted(Path("pages").glob("*.py"))


@pytest.mark.parametrize("page_path", PAGES, ids=[p.stem for p in PAGES])
def test_streamlit_page_renders_without_exception(page_path):
    """Verify that every Streamlit page compiles, mounts, and runs without uncaught exceptions."""
    at = AppTest.from_file(str(page_path))
    at.session_state["owner_authenticated"] = True
    at.session_state["user_id"] = "shivansh_electronics_hardware"
    at.session_state["business_name"] = "Shivansh Electronics and Hardware"
    at.run(timeout=30)

    if at.exception:
        pytest.fail(f"Page {page_path.name} failed with: {at.exception[0].message}")

