"""Run the private local Learning pilot without loading portfolio configuration."""
import os
from pathlib import Path
import sys

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.learning_pilot import main  # noqa: E402

if __name__ == "__main__":
    main()
