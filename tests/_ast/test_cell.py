# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Awaitable

import pytest

from marimo import _loggers
from marimo._ast.app import App
from marimo._ast.cell import CellConfig


class TestCellRun:
    @staticmethod
    def test_cell_basic() -> None:
        def f() -> tuple[int]:
            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert not cell.refs
        assert cell.defs == set(["x"])
        assert not cell._is_coroutine
        assert cell.run() == ("output", {"x": 4})

    @staticmethod
    async def test_async_cell_basic() -> None:
        async def f(asyncio) -> tuple[int]:
            await asyncio.sleep(0)

            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert cell.refs == {"asyncio"}
        assert cell.defs == {"x"}
        assert cell._is_coroutine

        import asyncio

        ret = cell.run(asyncio=asyncio)
        assert isinstance(ret, Awaitable)
        assert await ret == ("output", {"x": 4})

    @staticmethod
    def test_unknown_ref_raises() -> None:
        def f() -> None: ...

        app = App()
        cell = app.cell(f)
        with pytest.raises(ValueError) as einfo:
            cell.run(foo=1)
        assert "unexpected argument" in str(einfo.value)

    @staticmethod
    def test_substituted_ref_basic() -> None:
        app = App()

        @app.cell
        def g():
            x = 0
            y = 1
            return (x, y)

        @app.cell
        def h(x, y):
            z = x + y
            return (z,)

        assert h.run() == (None, {"z": 1})
        assert h.run(x=1) == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})
        assert h.run(x=1, y=2) == (None, {"z": 3})

    @staticmethod
    def test_substituted_ref_chain() -> None:
        app = App()

        @app.cell
        def f():
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x + 1
            return (y,)

        @app.cell
        def h(y):
            z = 2 * y
            return (z,)

        assert h.run() == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})

        with pytest.raises(ValueError) as e:
            h.run(x=1)
        assert "unexpected argument" in str(e.value)

    @staticmethod
    def test_async_parent() -> None:
        app = App()

        @app.cell
        async def g(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def h(x):
            y = x
            return (y,)

        assert g._is_coroutine
        # h is a coroutine because it depends on the execution of an async
        # function
        assert h._is_coroutine

    @staticmethod
    def test_async_chain() -> None:
        app = App()

        @app.cell
        async def f(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x
            return (y,)

        @app.cell
        def h(y):
            z = y
            return (z,)

        assert f._is_coroutine
        assert g._is_coroutine
        assert h._is_coroutine

    @staticmethod
    def test_empty_cell() -> None:
        app = App()

        @app.cell
        def f() -> None:
            return

        assert f.run() == (None, {})

    @staticmethod
    def test_conditional_def() -> None:
        app = App()

        @app.cell
        def f():
            if False:
                x = 0
            return (x,)

        # "x" was statically declared
        assert f.defs == {"x"}
        # "x" should not be in returns because it wasn't defined at runtime
        assert f.run() == (None, {})

    @staticmethod
    def test_import() -> None:
        from cell_data.named_cells import f, g, h

        assert f.name == "f"
        assert g.name == "g"
        assert h.name == "h"

        assert f.run() == (None, {"x": 0})
        assert g.run() == (None, {"y": 1})
        assert h.run() == (2, {"z": 2})

        assert g.run(x=1) == (None, {"y": 2})
        assert h.run(y=2) == (3, {"z": 3})

    @staticmethod
    def test_unhashable_import() -> None:
        from cell_data.named_cells import (
            unhashable_defined,
            unhashable_override_required,
        )

        assert unhashable_defined.name == "unhashable_defined"
        assert (
            unhashable_override_required.name == "unhashable_override_required"
        )

        assert unhashable_override_required.run(unhashable={0, 1}) == (
            {0, 1},
            {},
        )
        assert unhashable_defined.run() == (
            {0, 1, 2},
            {"unhashable": {0, 1, 2}},
        )

    @staticmethod
    def test_direct_call() -> None:
        from cell_data.named_cells import h, multiple, unhashable_defined

        assert h(1) == 2
        assert multiple() == (0, 1)
        assert unhashable_defined() == {0, 1, 2}

    @staticmethod
    def test_direct_call_with_global() -> None:
        old = os.environ.pop("PYTEST_CURRENT_TEST")
        old_version = os.environ.pop("PYTEST_VERSION")
        try:
            if "cell_data.named_cells" in sys.modules:
                del sys.modules["cell_data.named_cells"]
            from cell_data.named_cells import called_with_global

            # NB. depends on a variable `a` defined on module level.
            assert called_with_global(1) == 2
            assert called_with_global(x=1) == 2

            # Raise errors
            with pytest.raises(TypeError) as e:
                called_with_global(1, 1)

            with pytest.raises(TypeError) as e:
                called_with_global(x=1, a=1)
            assert "unexpected argument" in str(e.value)

            with pytest.raises(TypeError) as e:
                called_with_global(a=1)
            assert "unexpected argument" in str(e.value)

        finally:
            os.environ["PYTEST_CURRENT_TEST"] = old
            os.environ["PYTEST_VERSION"] = old_version

    @staticmethod
    def test_mismatch_args(app, caplog) -> None:
        # poor practice, but possible cell.
        @app.cell
        def basic(lots, of_, incorrect, args):  # noqa: ARG001
            1  # noqa: B018
            return

        assert basic.run() == (1, {})
        assert len(caplog.records) == 0
        with caplog.at_level(logging.WARNING):
            _loggers.marimo_logger().propagate = True
            assert basic() == 1
        assert len(caplog.records) == 1
        assert "signature" in caplog.text

    @staticmethod
    def test_direct_cyclic_call(app) -> None:
        # poor practice, but possible cell.
        @app.cell
        def cyclic():
            a = 1
            if False:
                a = b  # noqa: F821
            else:
                b = a
            b  # noqa: B018
            return

        assert cyclic.run() == (1, {"a": 1, "b": 1})
        assert cyclic() == 1


class TestReusableCell:
    @staticmethod
    def test_run_ok_with_setup_dep(app) -> None:
        with app.setup:
            z = 1

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            # non transitive
            x = y - z
            x  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"x": 0}

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"x": 1}

        output, defs = uses_setup.run(z=2)
        assert output == -1
        assert defs == {"x": -1}

    @staticmethod
    def test_run_ok_with_setup_dep_rev_abc(app) -> None:
        # Arguments are alphabetized
        with app.setup:
            x = 1

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            z = y - x
            z  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"z": 0}, dict(defs)

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"z": 1}

        output, defs = uses_setup.run(x=2)
        assert output == -1
        assert defs == {"z": -1}

    @staticmethod
    def test_run_setup_declares_more(app) -> None:
        # Arguments are alphabetized
        with app.setup:
            x = 1
            # a is important because it's an additional def that gets
            # inserted into the runtime
            a = 1

        @app.function
        def something_normally_scoped_for_a():
            return 1 + a

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            z = 0 * something_normally_scoped_for_a() + y - x
            z  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"z": 0}, dict(defs)

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"z": 1}

        output, defs = uses_setup.run(x=2)
        assert output == -1
        assert defs == {"z": -1}


class TestDecoratedCells:
    @staticmethod
    def test_functool_wrapped(app) -> None:
        with app.setup:
            from functools import cache

        @app.function
        @cache
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3
        assert add.cache_info().hits == 0
        assert add(1, 2) == 3
        assert add.cache_info().hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }

    @staticmethod
    def test_cache_wrapped(app) -> None:
        with app.setup:
            from marimo import cache

        @app.function
        @cache
        def add(a: int, b: int) -> int:
            return a + b

        @app.cell
        def _() -> None:
            # Calling with the same app yields the same runner
            assert add(1, 2) == 3
            assert add.hits == 0

        # Calling with the same app yields the same runner
        assert add(1, 2) == 3
        assert add.hits == 0
        assert add(1, 2) == 3
        assert add.hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }

    @staticmethod
    def test_persistent_cache_wrapped(app) -> None:
        with app.setup:
            import shutil

            # Create a temporary cache directory
            import tempfile

            from marimo import persistent_cache as cache

            cache_dir = tempfile.mkdtemp()

        @app.function
        @cache(save_path=cache_dir)
        def add(a: int, b: int) -> int:
            return a + b

        @app.cell
        def _() -> None:
            # Calling with the same app yields the same runner
            assert add(1, 2) == 3
            # Because the cache is persistent
            assert add.hits == 1
            # Clean up the cache directory after the test
            shutil.rmtree(cache_dir)

        # Calling with the same app yields the same runner
        assert add(1, 2) == 3
        assert add.hits == 0
        assert add(1, 2) == 3
        assert add.hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }


def help_smoke() -> None:
    app = App()

    @app.cell
    async def f(x) -> None:
        await x
        return

    @app.cell
    def g() -> None:
        return

    assert "Async" in f._help().text
    assert "Async" not in g._help().text


def test_cell_config_asdict_without_defaults():
    config = CellConfig()
    assert config.asdict_without_defaults() == {}

    config = CellConfig(hide_code=True)
    assert config.asdict_without_defaults() == {"hide_code": True}

    config = CellConfig(hide_code=False)
    assert config.asdict_without_defaults() == {}


def test_is_different_from_default():
    config = CellConfig(hide_code=True)
    assert config.is_different_from_default()

    config = CellConfig(hide_code=False)
    assert not config.is_different_from_default()
