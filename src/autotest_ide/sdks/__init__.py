"""SDK protocol adapters package.

Each sub-package provides a ``PocoProtocol`` implementation for a specific
game SDK.  The ``PROTOCOL_REGISTRY`` maps a short name (used by the UI
combo box and the runner ``--protocol`` CLI flag) to a
``package.module:ClassName`` spec.

To add a new SDK:

1. Create ``sdks/<name>/__init__.py`` and ``sdks/<name>/protocol.py``
2. Implement a ``PocoProtocol`` subclass
3. Add an entry to ``PROTOCOL_REGISTRY`` below

The UI and CLI pick up new entries automatically.
"""

PROTOCOL_REGISTRY = {
    "jx4": "autotest_ide.sdks.jx4.protocol:JX4Protocol",
}
