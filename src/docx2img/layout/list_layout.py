"""List numbering engine — format counters and label text."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..model.numbering import NumberingTable, LevelDef
from ..model.enums import NumberFormat


class NumberingEngine:
    """Track list counters and produce label strings."""

    def __init__(self, table: NumberingTable):
        self.table = table
        # counters[(num_id, level)] = current value
        self._counters: Dict[Tuple[int, int], int] = {}

    def next_label(self, num_id: int, level: int) -> Tuple[str, Optional[LevelDef]]:
        """Advance counter for (num_id, level) and return (label, level_def)."""
        lvl = self.table.get_level(num_id, level)
        if lvl is None:
            return ("", None)

        # Reset deeper levels
        for (nid, lv) in list(self._counters.keys()):
            if nid == num_id and lv > level:
                del self._counters[(nid, lv)]

        key = (num_id, level)
        if key not in self._counters:
            self._counters[key] = lvl.start
        else:
            self._counters[key] += 1

        label = self._format_label(num_id, level, lvl)
        return label, lvl

    def peek_indent(self, num_id: int, level: int) -> Tuple[float, float]:
        """Return (left_indent_pt, hanging_pt) for level."""
        lvl = self.table.get_level(num_id, level)
        if not lvl:
            return 0.0, 0.0
        return lvl.left, lvl.hanging

    def _format_label(self, num_id: int, level: int, lvl: LevelDef) -> str:
        # Build values for %1..%9 from counters
        values = {}
        for i in range(0, level + 1):
            key = (num_id, i)
            li = self.table.get_level(num_id, i)
            if key in self._counters:
                values[i + 1] = self._format_number(self._counters[key], li.format if li else NumberFormat.DECIMAL)
            elif li:
                values[i + 1] = self._format_number(li.start, li.format)

        text = lvl.text or "%1."
        for i in range(9, 0, -1):
            text = text.replace(f"%{i}", values.get(i, ""))
        return text

    def _format_number(self, n: int, fmt: NumberFormat) -> str:
        if fmt == NumberFormat.DECIMAL:
            return str(n)
        if fmt == NumberFormat.UPPER_LETTER:
            return self._to_alpha(n, upper=True)
        if fmt == NumberFormat.LOWER_LETTER:
            return self._to_alpha(n, upper=False)
        if fmt == NumberFormat.UPPER_ROMAN:
            return self._to_roman(n, upper=True)
        if fmt == NumberFormat.LOWER_ROMAN:
            return self._to_roman(n, upper=False)
        if fmt == NumberFormat.BULLET:
            return "•"
        if fmt == NumberFormat.CHINESE_COUNTING:
            return self._to_chinese(n)
        if fmt == NumberFormat.NONE:
            return ""
        return str(n)

    @staticmethod
    def _to_alpha(n: int, upper: bool = True) -> str:
        if n <= 0:
            return ""
        result = []
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result.append(chr(ord('A' if upper else 'a') + rem))
        return "".join(reversed(result))

    @staticmethod
    def _to_roman(n: int, upper: bool = True) -> str:
        vals = [
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
        ]
        result = []
        for v, s in vals:
            while n >= v:
                result.append(s)
                n -= v
        text = "".join(result)
        return text if upper else text.lower()

    @staticmethod
    def _to_chinese(n: int) -> str:
        digits = "零一二三四五六七八九"
        if n <= 0:
            return digits[0]
        if n < 10:
            return digits[n]
        if n == 10:
            return "十"
        if n < 20:
            return "十" + digits[n % 10]
        if n < 100:
            tens, ones = divmod(n, 10)
            return digits[tens] + "十" + (digits[ones] if ones else "")
        return str(n)
