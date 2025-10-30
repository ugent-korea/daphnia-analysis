import re, datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from app.core.database import get_data

CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

def canonical_core(s: str) -> str:
    s = (s or "").strip().split('_')[0]
    m = CORE_RE.match(s)
    if not m:
        raise ValueError(f"Bad core id: {s}")
    word = m.group(1).upper()
    nums = re.findall(r'\d+', m.group(2))
    if not nums:
        raise ValueError("Core must include at least one number, e.g. 'E.1'")
    nums = [str(int(n)) for n in nums]
    return word + '.' + '.'.join(nums)

def get_mother_row(user_input: str):
    data = get_data()
    raw = (user_input or "").strip()
    if not raw:
        return None, None

    try:
        core = canonical_core(raw)
    except Exception:
        return None, None

    if '_' in raw:
        suf = raw.split('_', 1)[1]
        full = data["core_to_suffix"].get(core, {}).get(suf)
        if not full:
            full = raw if raw in data["by_full"] else None
        if not full:
            return None, None
    else:
        full = data["core_latest"].get(core)
        if not full:
            return None, None

    return data["by_full"][full], full

def get_children_ids(parent_full_id: str):
    return get_data()["children_by_origin"].get(parent_full_id, [])

def is_mother_alive(parent_row: dict) -> bool:
    """Check if a mother is alive based on status and death_date."""
    status = str(parent_row.get("status", "")).strip().lower()
    death_date = str(parent_row.get("death_date", "")).strip()
    return (status == "" or status not in ["dead", "deceased", "died"]) and death_date == ""

def _parse_core(core: str):
    core = canonical_core(core)
    parts = core.split('.')
    set_word = parts[0]
    gen = int(parts[1])
    path = [int(x) for x in parts[2:]]
    return set_word, gen, path

def _format_core(set_word, gen, path):
    s = f"{set_word}.{gen}"
    if path:
        s += "." + ".".join(map(str, path))
    return s

def _next_child_index(parent_core, child_ids):
    want = parent_core + '.'
    idx = []
    for cid in child_ids:
        ccore = cid.split('_')[0]
        if ccore.startswith(want):
            tail = ccore[len(want):]
            if re.fullmatch(r'\d+', tail):
                idx.append(int(tail))
    return (max(idx) + 1) if idx else 1

def _next_generation_for_set_cached(set_word: str) -> int:
    data = get_data()
    max_gen = data["set_max_gen"].get(set_word, 1)
    return max_gen + 1

def _alive_count_in_set(set_word: str) -> int:
    data = get_data()
    cnt = 0
    for row in data["by_full"].values():
        if (row.get("set_label") or "").upper() == set_word.upper():
            # Alive = both status is empty/not dead AND death_date is empty
            status = str(row.get("status", "")).strip().lower()
            death_date = str(row.get("death_date", "")).strip()
            is_alive = (status == "" or status not in ["dead", "deceased", "died"]) and death_date == ""
            if is_alive:
                cnt += 1
    return cnt

def compute_child_and_discard(parent_row, child_ids):
    parent_core_raw = parent_row["mother_id"].split('_')[0]
    set_word, gen, path = _parse_core(parent_core_raw)
    parent_core = _format_core(set_word, gen, path)

    # Founder = only letter + generation (no path), e.g., E.1, E.2, E.3
    # Founders can have INFINITE broods, never reset
    if len(path) == 0:
        next_idx = _next_child_index(parent_core, child_ids)
        suggested_core = f"{parent_core}.{next_idx}"
        return suggested_core, False, f"Founder {parent_core}: next brood={next_idx} (founders never discard/reset)."

    # Non-founders: maximum 3 broods that extend path, then reset to new founder generations
    next_idx = _next_child_index(parent_core, child_ids)

    if next_idx == 1:
        suggested_core = f"{parent_core}.1"
        return suggested_core, True, f"{parent_core}: 1st subbrood → discard."

    if next_idx == 2:
        suggested_core = f"{parent_core}.2"
        return suggested_core, False, f"{parent_core}: 2nd subbrood → keep."

    if next_idx == 3:
        suggested_core = f"{parent_core}.3"
        return suggested_core, False, f"{parent_core}: 3rd subbrood → keep."

    # 4th+ broods: each becomes a new founder generation
    # 4th → next available generation, 5th → next+1, 6th → next+2, etc.
    base_new_gen = _next_generation_for_set_cached(set_word)
    generation_offset = next_idx - 4  # 4th→0, 5th→1, 6th→2, etc.
    new_gen_number = base_new_gen + generation_offset
    new_core = f"{set_word}.{new_gen_number}"
    return new_core, False, f"{parent_core}: {next_idx}th subbrood → RESET to new founder generation {new_core}."
