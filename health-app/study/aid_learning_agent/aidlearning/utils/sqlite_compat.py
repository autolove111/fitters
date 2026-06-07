"""SQLite compatibility layer with FTS5 support.

Tries to import ``pysqlite3`` (which bundles FTS5) first, then falls
back to the standard library ``sqlite3``.  This ensures FTS5 is
available in Docker (where ``pysqlite3-binary`` is installed) while
still working on local dev machines without it.

Usage::

    from aidlearning.utils.sqlite_compat import sqlite3
"""

try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3

__all__ = ["sqlite3"]
