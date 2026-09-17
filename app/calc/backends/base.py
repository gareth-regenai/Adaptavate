"""Backend interface. The rest of the app never imports a backend directly."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Backend(ABC):
    """Turns model inputs into model outputs. Implementation detail below this line."""

    name: str = "base"

    @abstractmethod
    def compute(
        self, model_inputs: dict[str, float], include_internal: bool = False
    ) -> dict[str, float | None]:
        """Write inputs to the workbook, recalculate, read the outputs back.

        include_internal adds the internal-only figures. Callers must only set
        it for an authorised internal request.
        """


def scalar(val) -> float | None:
    """Coerce whatever a backend returns into a plain float or None.

    The formulas library hands back array-like wrappers; LibreOffice hands back
    whatever openpyxl read. Normalise here so callers never care.
    """
    if val is None:
        return None
    if hasattr(val, "value"):
        val = val.value
        for accessor in ((0, 0), 0):
            try:
                val = val[accessor]
                break
            except Exception:
                continue
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check
