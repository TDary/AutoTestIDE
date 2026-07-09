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

import importlib

from autotest_ide.core.protocol_base import PocoProtocol

PROTOCOL_REGISTRY = {
    "jx4": "autotest_ide.sdks.jx4.protocol:JX4Protocol",
}


def load_protocol(sdk_name: str) -> PocoProtocol:
    """Load and instantiate a protocol adapter by name or spec.

    Accepts three forms:

    1. A registry short name, e.g. ``"jx4"``  (looked up in PROTOCOL_REGISTRY)
    2. A fully qualified ``package.module:ClassName`` spec, e.g.
       ``"autotest_ide.sdks.jx4.protocol:JX4Protocol"``
    3. A bare package name, e.g. ``"jx4"``  (resolved as
       ``autotest_ide.sdks.<name>.protocol:<NAME>Protocol``)

    Returns a freshly instantiated ``PocoProtocol``.

    Raises ``ValueError`` if the SDK name is not found in the registry
    and cannot be resolved as a package.
    """
    # Case 1: direct spec with colon separator
    if ":" in sdk_name:
        module_path, class_name = sdk_name.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()

    # Case 2: registry short name
    if sdk_name in PROTOCOL_REGISTRY:
        full_spec = PROTOCOL_REGISTRY[sdk_name]
        module_path, class_name = full_spec.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()

    # Case 3: try sdks package by name
    try:
        mod = importlib.import_module(f"autotest_ide.sdks.{sdk_name}.protocol")
        cls = getattr(mod, f"{sdk_name.upper()}Protocol", None)
        if cls:
            return cls()
    except (ImportError, AttributeError):
        pass

    raise ValueError(
        f"Unknown SDK '{sdk_name}'. Available: {', '.join(PROTOCOL_REGISTRY.keys())}"
    )
