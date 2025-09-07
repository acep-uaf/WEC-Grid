# sync_example.py  (repo root)
import shutil, glob, pathlib

# Go up 2 levels from .github/workflows/ to get repo root
root = pathlib.Path(__file__).resolve().parent.parent.parent
docs_nb = root / "docs" / "examples" / "jupyter_notebooks"
(docs_nb / "grid_models").mkdir(parents=True, exist_ok=True)

# notebooks
for nb in glob.glob(str(root / "examples" / "*.ipynb")):
    shutil.copy2(nb, docs_nb)

# optional: grid models used by docs pages
gm_src = root / "examples" / "grid_models"
if gm_src.exists():
    for f in gm_src.iterdir():
        if f.is_file():
            shutil.copy2(f, docs_nb / "grid_models")

# optional: preloaded DB used by docs pages
db_src = root / "examples" / "WECGrid.db"
if db_src.exists():
    (root / "docs" / "examples").mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_src, root / "docs" / "examples" / "WECGrid.db")