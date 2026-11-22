"""Single deterministic compensation engine (pure Python, no Odoo imports)."""
try:
    from . import policy  # noqa: F401
    from . import grade_policy  # noqa: F401
    from . import multipliers  # noqa: F401
    from . import preview  # noqa: F401
    from . import run  # noqa: F401
    from . import operations  # noqa: F401
    from . import sales  # noqa: F401
except ImportError:
    pass
