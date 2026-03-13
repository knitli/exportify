import time

from pathlib import Path

from exportify.validator.validator import LateImportValidator


def run_benchmark():
    # Setup dummy files
    tmp_dir = Path("bench_tmp")
    tmp_dir.mkdir(exist_ok=True)
    files = []

    # Create large files
    content = "from typing import TYPE_CHECKING\n" * 100
    content += "if TYPE_CHECKING:\n"
    content += "    import os\n" * 100
    content += "def foo():\n"
    content += "    os = lateimport('os', 'os')\n" * 100

    for i in range(100):
        f = tmp_dir / f"test_file_{i}.py"
        f.write_text(content)
        files.append(f)

    validator = LateImportValidator(project_root=tmp_dir)

    start = time.time()
    for _ in range(50):
        validator.validate(file_paths=files)
    end = time.time()

    # Cleanup
    for f in files:
        f.unlink()
    tmp_dir.rmdir()

    print(f"Validation took {end - start:.4f} seconds for 5000 large files")


if __name__ == "__main__":
    run_benchmark()
