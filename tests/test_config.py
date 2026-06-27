import tempfile
import tomllib
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer import config


def main() -> None:
    original_path = config.USER_CONFIG_PATH
    with tempfile.TemporaryDirectory() as temp_dir:
        config.USER_CONFIG_PATH = Path(temp_dir) / "config.toml"
        try:
            config.write_user_config(
                {
                    "output": {
                        "preset": "Legal / case",
                        "include_date": True,
                        "presets": {
                            "Legal / case": {
                                "fields": [
                                    "Date",
                                    "Reference",
                                    "Document type",
                                ],
                            },
                        },
                    },
                }
            )
            with config.USER_CONFIG_PATH.open("rb") as source:
                written = tomllib.load(source)
        finally:
            config.USER_CONFIG_PATH = original_path

    assert written["output"]["preset"] == "Legal / case"
    assert written["output"]["include_date"] is True
    assert written["output"]["presets"]["Legal / case"]["fields"] == [
        "Date",
        "Reference",
        "Document type",
    ]
    print("PASS: nested config writing")


if __name__ == "__main__":
    main()
