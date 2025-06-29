# generate_version_file.py

"""
Helper script for generating file_version_info.txt for PyInstaller builds.

This script extracts version and metadata directly from pyproject.toml.

Usage:
    python generate_version_file.py

- Reads the [project] section from pyproject.toml.
- Writes a file_version_info.txt file in the format expected by PyInstaller.
- Keeps version and author info in sync with the main project metadata.
"""

import sys

try:
    # Try to use the built-in tomllib (Python 3.11+)
    import tomllib
except ImportError:
    # If not available, fall back to tomli (for Python <3.11)
    try:
        import tomli as tomllib  # type: ignore[import]
    except ImportError:
        sys.exit("Error: tomllib or tomli is required. Please run 'pip install tomli'.")

print("Reading metadata from pyproject.toml...")
try:
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)["project"]

    APP_VERSION = pyproject_data["version"]
    APP_NAME = pyproject_data["name"]
    APP_AUTHOR = pyproject_data["authors"][0]["name"]
    APP_DESCRIPTION = pyproject_data["description"]

except (FileNotFoundError, KeyError) as e:
    sys.exit(f"Error: Could not read required metadata from pyproject.toml. {e}")

# PyInstaller expects a 4-part version tuple (e.g., 1, 2, 3, 0)
version_parts = APP_VERSION.split(".") + ["0"] * (4 - len(APP_VERSION.split(".")))
version_tuple_str = ", ".join(version_parts[:4])

VERSION_FILE_PATH = "file_version_info.txt"
print(f"Generating {VERSION_FILE_PATH} for version {APP_VERSION}...")

# Template for the version info file (used by PyInstaller)
file_content = f"""
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple_str}),
    prodvers=({version_tuple_str}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{APP_AUTHOR}'),
        StringStruct('FileDescription', '{APP_DESCRIPTION}'),
        StringStruct('FileVersion', '{APP_VERSION}'),
        StringStruct('InternalName', '{APP_NAME}'),
        StringStruct('LegalCopyright', 'Copyright © 2025 {APP_AUTHOR}'),
        StringStruct('OriginalFilename', '{APP_NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

try:
    with open(VERSION_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(file_content)
    print("Successfully created file_version_info.txt.")
except IOError as e:
    sys.exit(f"Error writing to {VERSION_FILE_PATH}: {e}")
