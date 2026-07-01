"""Default Poco text-command protocol.

This re-exports ``PocoTextProtocol`` from the core module so that
``--protocol poco`` resolves to the standard adapter.
"""
from autotest_ide.core.protocol_poco import PocoTextProtocol

__all__ = ["PocoTextProtocol"]
