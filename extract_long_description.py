import tomllib
import os

with open("pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)

readme_path = pyproject["project"]["readme"]

if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as readme_file:
        print(readme_file.read())
else:
    raise FileNotFoundError(f"{readme_path} not found.")
