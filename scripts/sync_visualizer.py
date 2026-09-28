"""Copy the standalone teaching HTML into package assets for the /architecture route."""

from pathlib import Path
from shutil import copyfile


def main():
    """Refresh the served asset from docs/architecture_visualizer.html."""
    root = Path(__file__).resolve().parents[1]
    source = root / "docs" / "architecture_visualizer.html"
    target = root / "app" / "static" / "architecture_visualizer.html"
    copyfile(source, target)
    print(f"Synchronized {target.relative_to(root)}")


if __name__ == "__main__":
    main()
