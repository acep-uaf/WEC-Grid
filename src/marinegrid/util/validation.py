"""
Runtime validation utilities for Marine-Grid.

File: src/marinegrid/util/validation.py

Provides decorators and utilities for runtime type checking and validation,
making code more robust and easier to debug.
"""

# Standard library
import functools
import inspect
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    get_args,
    get_origin,
    get_type_hints,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# Third-party
import pandas as pd
import numpy as np


F = TypeVar("F", bound=Callable[..., Any])


def _get_type_name(tp: Any) -> str:
    """Get a human-readable name for a type."""
    if tp is type(None):
        return "None"
    if hasattr(tp, "__name__"):
        return tp.__name__
    if hasattr(tp, "_name"):
        return tp._name
    return str(tp)


def _format_expected_types(types: Tuple[Type, ...]) -> str:
    """Format a tuple of types for error messages."""
    if len(types) == 1:
        return _get_type_name(types[0])
    names = [_get_type_name(t) for t in types]
    return f"{', '.join(names[:-1])} or {names[-1]}"


def _is_instance_of_type(value: Any, expected_type: Any) -> bool:
    """
    Check if a value matches an expected type, including generics.

    Handles Union, Optional, List, Dict, and other typing constructs.
    """
    # Handle None
    if value is None:
        if expected_type is type(None):
            return True
        origin = get_origin(expected_type)
        if origin is Union:
            return type(None) in get_args(expected_type)
        return False

    # Get origin for generic types (List, Dict, Union, etc.)
    origin = get_origin(expected_type)

    # Handle Union (including Optional which is Union[X, None])
    if origin is Union:
        return any(_is_instance_of_type(value, arg) for arg in get_args(expected_type))

    # Handle List, Set, Tuple
    if origin in (list, List):
        if not isinstance(value, list):
            return False
        args = get_args(expected_type)
        if args:
            return all(_is_instance_of_type(item, args[0]) for item in value)
        return True

    if origin in (set, Set):
        if not isinstance(value, set):
            return False
        args = get_args(expected_type)
        if args:
            return all(_is_instance_of_type(item, args[0]) for item in value)
        return True

    if origin in (tuple, Tuple):
        if not isinstance(value, tuple):
            return False
        args = get_args(expected_type)
        if args:
            if len(args) == 2 and args[1] is ...:
                return all(_is_instance_of_type(item, args[0]) for item in value)
            if len(value) != len(args):
                return False
            return all(_is_instance_of_type(v, t) for v, t in zip(value, args))
        return True

    # Handle Dict
    if origin in (dict, Dict):
        if not isinstance(value, dict):
            return False
        args = get_args(expected_type)
        if args and len(args) == 2:
            key_type, val_type = args
            return all(
                _is_instance_of_type(k, key_type) and _is_instance_of_type(v, val_type)
                for k, v in value.items()
            )
        return True

    # Handle regular types
    if origin is not None:
        return isinstance(value, origin)

    # Direct isinstance check
    try:
        return isinstance(value, expected_type)
    except TypeError:
        # Some types don't support isinstance
        return False


def validate_types(func: F) -> F:
    """
    Decorator that validates function argument types at runtime.

    Uses type hints from the function signature to validate arguments.
    Raises TypeError with clear messages on validation failure.

    Example:
        @validate_types
        def process(data: pd.DataFrame, count: int) -> bool:
            ...

        process("not a df", 5)  # Raises TypeError
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get type hints and signature
        try:
            hints = get_type_hints(func)
        except Exception:
            # If we can't get hints, just call the function
            return func(*args, **kwargs)

        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Build dict of argument name -> value
        bound_args = {}
        for i, arg in enumerate(args):
            if i < len(params):
                bound_args[params[i]] = arg
        bound_args.update(kwargs)

        # Validate each argument against its type hint
        for param_name, value in bound_args.items():
            if param_name in hints and param_name != "return":
                expected_type = hints[param_name]
                if not _is_instance_of_type(value, expected_type):
                    actual_type = type(value).__name__
                    raise TypeError(
                        f"{func.__name__}() argument '{param_name}' must be "
                        f"{expected_type}, got {actual_type}: {value!r}"
                    )

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_not_none(*param_names: str) -> Callable[[F], F]:
    """
    Decorator that validates specified parameters are not None.

    Example:
        @validate_not_none("data", "name")
        def process(data, name, optional=None):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            # Build dict of argument name -> value
            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(params):
                    bound_args[params[i]] = arg
            bound_args.update(kwargs)

            # Check specified params
            for param_name in param_names:
                if param_name in bound_args and bound_args[param_name] is None:
                    raise ValueError(
                        f"{func.__name__}() argument '{param_name}' cannot be None"
                    )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_path(
    param_name: str,
    must_exist: bool = False,
    allowed_extensions: Optional[Set[str]] = None,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Callable[[F], F]:
    """
    Decorator that validates a path parameter.

    Args:
        param_name: Name of the parameter to validate.
        must_exist: If True, path must exist.
        allowed_extensions: Set of allowed extensions (e.g., {".raw", ".sav"}).
        must_be_file: If True, path must be a file.
        must_be_dir: If True, path must be a directory.

    Example:
        @validate_path("case_file", must_exist=True, allowed_extensions={".raw", ".sav"})
        def load_case(case_file: str | Path):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            # Get the path value
            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(params):
                    bound_args[params[i]] = arg
            bound_args.update(kwargs)

            if param_name not in bound_args:
                return func(*args, **kwargs)

            path_value = bound_args[param_name]

            # Type check
            if not isinstance(path_value, (str, Path)):
                raise TypeError(
                    f"{func.__name__}() argument '{param_name}' must be "
                    f"str or Path, got {type(path_value).__name__}"
                )

            path = Path(path_value).expanduser().resolve()

            # Existence check
            if must_exist and not path.exists():
                raise FileNotFoundError(
                    f"{func.__name__}(): {param_name} not found: {path}"
                )

            # File/dir check
            if must_be_file and path.exists() and not path.is_file():
                raise ValueError(
                    f"{func.__name__}(): {param_name} must be a file: {path}"
                )

            if must_be_dir and path.exists() and not path.is_dir():
                raise ValueError(
                    f"{func.__name__}(): {param_name} must be a directory: {path}"
                )

            # Extension check
            if allowed_extensions and path.suffix.lower() not in allowed_extensions:
                raise ValueError(
                    f"{func.__name__}(): {param_name} has unsupported extension "
                    f"'{path.suffix}', allowed: {allowed_extensions}"
                )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_range(
    param_name: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    exclusive_min: bool = False,
    exclusive_max: bool = False,
) -> Callable[[F], F]:
    """
    Decorator that validates a numeric parameter is within a range.

    Example:
        @validate_range("voltage", min_value=0.9, max_value=1.1)
        def check_voltage(voltage: float):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(params):
                    bound_args[params[i]] = arg
            bound_args.update(kwargs)

            if param_name not in bound_args:
                return func(*args, **kwargs)

            value = bound_args[param_name]

            if value is None:
                return func(*args, **kwargs)

            if min_value is not None:
                if exclusive_min:
                    if value <= min_value:
                        raise ValueError(
                            f"{func.__name__}(): {param_name} must be > {min_value}, got {value}"
                        )
                else:
                    if value < min_value:
                        raise ValueError(
                            f"{func.__name__}(): {param_name} must be >= {min_value}, got {value}"
                        )

            if max_value is not None:
                if exclusive_max:
                    if value >= max_value:
                        raise ValueError(
                            f"{func.__name__}(): {param_name} must be < {max_value}, got {value}"
                        )
                else:
                    if value > max_value:
                        raise ValueError(
                            f"{func.__name__}(): {param_name} must be <= {max_value}, got {value}"
                        )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_choice(
    param_name: str,
    choices: Set[Any],
    case_sensitive: bool = True,
) -> Callable[[F], F]:
    """
    Decorator that validates a parameter is one of the allowed choices.

    Example:
        @validate_choice("mode", choices={"pf", "opf", "lpf"}, case_sensitive=False)
        def run_analysis(mode: str):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(params):
                    bound_args[params[i]] = arg
            bound_args.update(kwargs)

            if param_name not in bound_args:
                return func(*args, **kwargs)

            value = bound_args[param_name]

            if value is None:
                return func(*args, **kwargs)

            check_value = value
            check_choices = choices

            if not case_sensitive and isinstance(value, str):
                check_value = value.lower()
                check_choices = {c.lower() if isinstance(c, str) else c for c in choices}

            if check_value not in check_choices:
                raise ValueError(
                    f"{func.__name__}(): {param_name} must be one of {choices}, got {value!r}"
                )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_dataframe(
    param_name: str,
    required_columns: Optional[Set[str]] = None,
    allow_empty: bool = True,
) -> Callable[[F], F]:
    """
    Decorator that validates a DataFrame parameter.

    Example:
        @validate_dataframe("data", required_columns={"bus", "p", "q"})
        def process_bus_data(data: pd.DataFrame):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(params):
                    bound_args[params[i]] = arg
            bound_args.update(kwargs)

            if param_name not in bound_args:
                return func(*args, **kwargs)

            df = bound_args[param_name]

            if df is None:
                return func(*args, **kwargs)

            if not isinstance(df, pd.DataFrame):
                raise TypeError(
                    f"{func.__name__}(): {param_name} must be a DataFrame, "
                    f"got {type(df).__name__}"
                )

            if not allow_empty and df.empty:
                raise ValueError(
                    f"{func.__name__}(): {param_name} cannot be empty"
                )

            if required_columns:
                missing = required_columns - set(df.columns)
                if missing:
                    raise ValueError(
                        f"{func.__name__}(): {param_name} missing required columns: {missing}"
                    )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


class TypedProperty:
    """
    Descriptor that validates property types on assignment.

    Example:
        class MyClass:
            name = TypedProperty(str)
            count = TypedProperty(int, default=0)
            data = TypedProperty((pd.DataFrame, type(None)), default=None)
    """

    def __init__(
        self,
        expected_type: Union[Type, Tuple[Type, ...]],
        default: Any = None,
        allow_none: bool = True,
    ):
        self.expected_type = expected_type
        self.default = default
        self.allow_none = allow_none
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.private_name, self.default)

    def __set__(self, obj, value):
        if value is None:
            if not self.allow_none:
                raise TypeError(
                    f"{obj.__class__.__name__}.{self.name} cannot be None"
                )
        elif not isinstance(value, self.expected_type):
            if isinstance(self.expected_type, tuple):
                type_str = _format_expected_types(self.expected_type)
            else:
                type_str = _get_type_name(self.expected_type)
            raise TypeError(
                f"{obj.__class__.__name__}.{self.name} must be {type_str}, "
                f"got {type(value).__name__}: {value!r}"
            )
        setattr(obj, self.private_name, value)


def require_initialized(*attrs: str) -> Callable[[F], F]:
    """
    Decorator that ensures specified instance attributes are not None before method call.

    Example:
        class Modeler:
            @require_initialized("network", "sbase")
            def solve(self):
                ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            for attr in attrs:
                if getattr(self, attr, None) is None:
                    raise RuntimeError(
                        f"{self.__class__.__name__}.{func.__name__}() requires "
                        f"'{attr}' to be initialized first"
                    )
            return func(self, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator
