from importlib.metadata import version

# Read from installed package metadata, which uv-dynamic-versioning sets at
# build time. Unlike poetry-dynamic-versioning, it does not rewrite source files.
__version__ = version("posit-bakery")
