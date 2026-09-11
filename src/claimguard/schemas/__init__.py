"""Typed contracts: every value that crosses a node boundary.

Submodules: ``claim`` (input + fixtures), ``handoffs`` (agent outputs),
``state`` (run status / terminal reason vocabulary), ``approval`` (human
gate). Import from the specific submodule rather than this package —
there are no re-exports here, to keep it obvious which model owns which
field when several modules define similarly named things.
"""
