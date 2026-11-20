import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))
# Never touch the real vault from tests
os.environ["PG_HOME"] = tempfile.mkdtemp(prefix="pg-test-")
os.environ.pop("PG_NLP", None)
