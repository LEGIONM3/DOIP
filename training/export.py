"""Export pipeline compiling model to TorchScript and manifest package."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from training.export_laya import export_model


def main():
    export_model(model_version="v1")


if __name__ == "__main__":
    main()
