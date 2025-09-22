from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple


@dataclass(frozen=True)
class ParsedCode:
    set_letter: str
    generation: int
    path: Tuple[int, ...]
    mmdd: Optional[str]

    @property
    def is_founder(self) -> bool:
        # TEAM 2.0 founder exception: only X1 (no dotted path)
        return self.generation == 1 and len(self.path) == 0

    def __str__(self) -> str:
        core = f"{self.set_letter}{self.generation}"
        if self.path:
            core += "." + ".".join(map(str, self.path))
        return f"{core}_{self.mmdd}" if self.mmdd else core


class CodeGenerator:
    """
    Generate new brood codes following the New Protocol.

    Inputs: mother code, next brood number (k), and date.
      - Founder (exactly X1): children are X1.k forever (no reset).
      - Non-founders: k=1..3 → extend as core.k ; k>=4 → reset to next top-level founder: X<next_gen>.

    NOTE: Since this is a single file, functions have to be limited and may not live up to standard.
    """

    def __init__(self, set_letter: str):
        self.set_letter = set_letter.upper()
        self.max_generation = 1  # starts at 1 (first founder); advanced on resets

    def _parse(self, code: str) -> ParsedCode:
        if "_" in code:
            core, mmdd = code.split("_", 1)
        else:
            core, mmdd = code, None

        if not core or not core[0].isalpha():
            raise ValueError(f"Invalid code: {code}")

        set_letter = core[0].upper()
        i = 1
        while i < len(core) and core[i].isdigit():
            i += 1
        if i == 1:
            raise ValueError(f"Missing generation in: {code}")
        generation = int(core[1:i])

        path: Tuple[int, ...] = ()
        if i < len(core):
            if not core[i:].startswith("."):
                raise ValueError(f"Invalid code: {code}")
            parts = core[i+1:].split(".")
            path = tuple(int(p) for p in parts if p)

        return ParsedCode(set_letter, generation, path, mmdd)

    def _format_mmdd(self, d: date) -> str:
        return d.strftime("%m%d")

    def next_brood(self, mother_code: str, brood_k: int, today: Optional[date] = None) -> str:
        """
        Generate the next brood code string
        """
        if brood_k < 1:
            raise ValueError("brood_k must be >= 1")

        mom = self._parse(mother_code)
        if today is None:
            today = date.today()
        mmdd = self._format_mmdd(today)

        core = f"{mom.set_letter}{mom.generation}"
        if mom.path:
            core += "." + ".".join(map(str, mom.path))

        # Founder X1 has no reset; always X1.k
        if mom.is_founder:
            return f"{core}.{brood_k}_{mmdd}"

        # Non-founders: k=1..3 → extend dotted; k>=4 → reset to next top-level founder
        if brood_k <= 3:
            return f"{core}.{brood_k}_{mmdd}"
        else:
            # Reset: become next generation founder (internal counter)
            self.max_generation = max(self.max_generation, mom.generation) + 1
            return f"{mom.set_letter}{self.max_generation}_{mmdd}"

    # -------- Next brood - code calculation --------
    def next_brood_and_discard(self, mother_code: str, brood_k: int, today: Optional[date] = None) -> tuple[str, bool]:
        """
        Returns (next_code, discard_flag) with simplified discard rules:
          - Founder X1: keep always
          - Non-founders: k=1 → discard; k=2 → keep; k=3 → keep; k>=4 → reset (keep)
        """
        if brood_k < 1:
            raise ValueError("brood_k must be >= 1")

        mom = self._parse(mother_code)
        if today is None:
            today = date.today()
        mmdd = self._format_mmdd(today)

        core = f"{mom.set_letter}{mom.generation}"
        if mom.path:
            core += "." + ".".join(map(str, mom.path))

        if mom.is_founder:
            return f"{core}.{brood_k}_{mmdd}", False  # founder: never discard

        if brood_k <= 3:
            code = f"{core}.{brood_k}_{mmdd}"
            discard = (brood_k == 1)  # 1st discard; 2nd/3rd keep
            return code, discard
        else:
            # reset to next top-level founder; keep
            self.max_generation = max(self.max_generation, mom.generation) + 1
            return f"{mom.set_letter}{self.max_generation}_{mmdd}", False


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    gen = CodeGenerator("A")

    # Founder A1
    print(gen.next_brood_and_discard("A1", 4, date(2025, 7, 8)))        # ('A1.4_0708', False)

    # Non-founder A1.1
    print(gen.next_brood_and_discard("A1.1_0701", 1, date(2025, 7, 10)))  # ('A1.1.1_0710', True)
    print(gen.next_brood_and_discard("A1.1_0701", 2, date(2025, 7, 15)))  # ('A1.1.2_0715', False)
    print(gen.next_brood_and_discard("A1.1_0701", 3, date(2025, 7, 20)))  # ('A1.1.3_0720', False)
    print(gen.next_brood_and_discard("A1.1_0701", 4, date(2025, 7, 25)))  # ('A2_0725', False)
