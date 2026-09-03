from pathlib import Path
import shutil
import sys


root = Path(sys.argv[1])
workers = int(sys.argv[2])
files = int(sys.argv[3])
if root.exists():
    shutil.rmtree(root)
for worker in range(workers):
    artifact = root / f"artifact-{worker}"
    basedir = artifact / "component" / "stage" / "bin"
    basedir.mkdir(parents=True)
    (artifact / "artifact_manifest.txt").write_text(
        "component/stage\n", encoding="utf-8"
    )
    for file_index in range(files):
        (basedir / f"file-{file_index:04}.dat").write_text(
            f"worker={worker};file={file_index}\n", encoding="utf-8"
        )
