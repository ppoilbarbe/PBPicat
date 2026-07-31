import itertools
import re
import uuid
from collections.abc import Iterator
from pathlib import Path


def _is_numeric(field: str) -> bool:
    return bool(field) and set(field) == {"#"}


def validate_schema(fields: list[str]) -> tuple[list[str], list[str], str | None]:
    """
    Returns (dirs, parts, numeric_spec) or raises ValueError.

    dirs        — consecutive non-empty non-numeric fields from start (directory path)
    parts       — all non-empty non-numeric fields (joined with '_' for filename)
    numeric_spec — the '#...' field if present, else None
    """
    numeric_fields = [(i, f) for i, f in enumerate(fields) if _is_numeric(f)]
    if len(numeric_fields) > 1:
        raise ValueError("Le schéma contient plusieurs zones numériques (une seule autorisée).")

    for f in fields:
        if f and "_" in f:
            raise ValueError(f"Le champ « {f} » contient le caractère « _ » interdit.")
        if f and "." in f:
            raise ValueError(f"Le champ « {f} » contient le caractère « . » interdit.")

    numeric_spec: str | None = numeric_fields[0][1] if numeric_fields else None

    parts: list[str] = [f for f in fields if f and not _is_numeric(f)]
    dirs: list[str] = parts

    if not parts and not numeric_spec:
        raise ValueError("Le schéma est vide : remplissez au moins une zone.")

    return dirs, parts, numeric_spec


def _numbering_pattern(basename: str) -> re.Pattern:
    if basename:
        return re.compile(rf"(?:^|_){re.escape(basename)}_(\d+)", re.IGNORECASE)
    return re.compile(r"(?:^|_)(\d+)(?:$|\.[^.]+$|_)", re.IGNORECASE)


def _used_numbers(
    dest_dir: Path, basename: str, extensions: set[str] | None = None, exclude: set[Path] | None = None
) -> set[int]:
    """Return every numeric suffix currently used in dest_dir for filenames containing
    basename_NNN, among files whose suffix (lowercased) is in `extensions`.

    Files in `exclude` (typically the sources of the rename batch itself, already resolved) are
    ignored, so a file about to be renamed away doesn't block its own current number from being
    reused.
    """
    pattern = _numbering_pattern(basename)
    exclude = exclude or set()
    used: set[int] = set()
    if dest_dir.exists():
        for f in dest_dir.iterdir():
            if f.resolve() in exclude:
                continue
            if extensions is not None and f.suffix.lower() not in extensions:
                continue
            m = pattern.search(f.name)
            if m:
                used.add(int(m.group(1)))
    return used


def find_max_number(dest_dir: Path, basename: str, extensions: set[str] | None = None) -> int:
    """Return the maximum numeric suffix used in dest_dir for filenames containing basename_NNN.

    If extensions is given, only files whose suffix (lowercased) is in that set are considered.
    """
    return max(_used_numbers(dest_dir, basename, extensions), default=0)


def _fill_gap_numbers(used: set[int], count: int) -> list[int]:
    """Return `count` distinct positive integers not in `used`, smallest first — filling gaps
    before continuing past the highest used number."""
    used = set(used)
    numbers = []
    n = 1
    while len(numbers) < count:
        if n not in used:
            numbers.append(n)
            used.add(n)
        n += 1
    return numbers


def build_rename_plan(
    dest_root: str,
    schema_fields: list[str],
    source_paths: list[Path],
    sidecar_extensions: list[str],
    image_extensions: list[str],
    video_extensions: list[str] | None = None,
    video_marker: str = "",
    video_marker_pos: int = 0,
    fill_gaps: bool = False,
) -> list[tuple[Path, Path]]:
    """
    Build (src, dst) pairs for source_paths and their sidecars.
    Raises ValueError for schema errors, FileExistsError if a destination already exists.

    For video files, video_marker is inserted at video_marker_pos within the schema parts.

    fill_gaps: when True, numbers are taken from the smallest missing gap in the existing
    sequence (per image/video counter) instead of always continuing after the current max.
    """
    dirs, parts, numeric_spec = validate_schema(schema_fields)

    basename = "_".join(parts)
    img_exts = {e.lower() for e in image_extensions}
    video_exts = {e.lower() for e in (video_extensions or [])}

    if video_marker:
        vid_parts: list[str] = list(parts)
        vid_parts.insert(min(video_marker_pos, len(vid_parts)), video_marker)
        video_basename = "_".join(vid_parts)
    else:
        vid_parts = list(parts)
        video_basename = basename

    dest_subdir = Path(dest_root)
    for d in dirs:
        dest_subdir = dest_subdir / d

    pairs: list[tuple[Path, Path]] = []

    min_digits = 0
    img_numbers: Iterator[int] = iter(())
    vid_numbers: Iterator[int] = iter(())
    if numeric_spec:
        min_digits = len(numeric_spec)
        if fill_gaps:
            exclude = {p.resolve() for p in source_paths}
            n_img = sum(1 for s in source_paths if s.suffix.lower() not in video_exts)
            n_vid = len(source_paths) - n_img
            used_img = _used_numbers(dest_subdir, basename, img_exts, exclude)
            used_vid = _used_numbers(dest_subdir, video_basename, video_exts, exclude)
            img_numbers = iter(_fill_gap_numbers(used_img, n_img))
            vid_numbers = iter(_fill_gap_numbers(used_vid, n_vid))
        else:
            img_numbers = itertools.count(find_max_number(dest_subdir, basename, img_exts) + 1)
            vid_numbers = itertools.count(find_max_number(dest_subdir, video_basename, video_exts) + 1)

    for src in source_paths:
        is_video = src.suffix.lower() in video_exts

        if numeric_spec:
            num = next(vid_numbers if is_video else img_numbers)
            num_str = str(num).zfill(min_digits)
        else:
            num_str = ""

        base_parts = vid_parts if is_video else list(parts)
        comps = [c for c in base_parts + ([num_str] if num_str else []) if c]
        stem = "_".join(comps)
        dst = dest_subdir / f"{stem}{src.suffix.lower()}"
        pairs.append((src, dst))

        for ext in sidecar_extensions:
            sc_src = src.parent / (src.stem + ext)
            if sc_src.exists():
                pairs.append((sc_src, dest_subdir / f"{stem}{ext}"))

    return pairs


def build_renumber_plan(
    schema_fields: list[str],
    source_paths: list[Path],
    sidecar_extensions: list[str],
    image_extensions: list[str],
    video_extensions: list[str] | None = None,
    video_marker: str = "",
    video_marker_pos: int = 0,
) -> list[tuple[Path, Path]]:
    """
    Build (src, dst) pairs for in-place renumbering starting from 1.
    Images and videos have separate counters.
    Only includes pairs where src != dst.
    Raises ValueError if the schema has no numeric field.
    """
    dirs, parts, numeric_spec = validate_schema(schema_fields)
    if not numeric_spec:
        raise ValueError("Le schéma ne contient pas de champ numérique (utilisez '#' pour définir un compteur).")

    min_digits = len(numeric_spec)
    video_exts = {e.lower() for e in (video_extensions or [])}

    if video_marker:
        vid_parts: list[str] = list(parts)
        vid_parts.insert(min(video_marker_pos, len(vid_parts)), video_marker)
    else:
        vid_parts = list(parts)

    pairs: list[tuple[Path, Path]] = []
    img_num = 1
    vid_num = 1

    for src in source_paths:
        is_video = src.suffix.lower() in video_exts
        if is_video:
            num_str = str(vid_num).zfill(min_digits)
            vid_num += 1
        else:
            num_str = str(img_num).zfill(min_digits)
            img_num += 1

        base_parts = vid_parts if is_video else list(parts)
        comps = [c for c in base_parts + [num_str] if c]
        stem = "_".join(comps)
        dst = src.parent / f"{stem}{src.suffix.lower()}"
        if src != dst:
            pairs.append((src, dst))

        for ext in sidecar_extensions:
            sc_src = src.parent / (src.stem + ext)
            if sc_src.exists():
                sc_dst = src.parent / f"{stem}{ext}"
                if sc_src != sc_dst:
                    pairs.append((sc_src, sc_dst))

    return pairs


def execute_renumber(pairs: list[tuple[Path, Path]]) -> None:
    """
    Execute in-place renaming via a two-phase temp rename to avoid conflicts.
    Rolls back on error.
    """
    if not pairs:
        return

    prefix = f".__pbpicat_{uuid.uuid4().hex[:8]}_"
    tmp_map = [(src, src.parent / f"{prefix}{i:04d}{src.suffix}", dst) for i, (src, dst) in enumerate(pairs)]

    done1: list[tuple[Path, Path]] = []
    try:
        for src, tmp, _dst in tmp_map:
            src.rename(tmp)
            done1.append((src, tmp))
    except OSError as exc:
        for src, tmp in reversed(done1):
            try:
                tmp.rename(src)
            except OSError:
                pass
        raise RuntimeError(f"Erreur lors du renommage : {exc}") from exc

    done2: list[tuple[Path, Path]] = []
    try:
        for _src, tmp, dst in tmp_map:
            tmp.rename(dst)
            done2.append((tmp, dst))
    except OSError as exc:
        for tmp, dst in reversed(done2):
            try:
                dst.rename(tmp)
            except OSError:
                pass
        for src, tmp, _dst in reversed(tmp_map):
            try:
                tmp.rename(src)
            except OSError:
                pass
        raise RuntimeError(f"Erreur lors du renommage : {exc}") from exc


def undo_renumber(pairs: list[tuple[Path, Path]]) -> None:
    """Reverse a renumber plan: new_dst → original_src via two-phase rename."""
    reversed_pairs = [(dst, src) for src, dst in pairs if dst != src]
    execute_renumber(reversed_pairs)


def undo_rename(pairs: list[tuple[Path, Path]]) -> None:
    """
    Reverse a rename plan: move each dst back to its original src.
    Raises FileNotFoundError if a dst no longer exists, FileExistsError if a src already exists.
    Rolls back on error. Removes empty destination directories afterwards.
    """
    missing = [dst for _, dst in pairs if not dst.exists()]
    if missing:
        raise FileNotFoundError("Fichier(s) introuvable(s) pour l'annulation : " + ", ".join(p.name for p in missing))
    conflicts = [src for src, _ in pairs if src.exists()]
    if conflicts:
        raise FileExistsError("Fichier(s) déjà présent(s) à la source : " + ", ".join(p.name for p in conflicts))

    moved: list[tuple[Path, Path]] = []
    try:
        for src, dst in pairs:
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.rename(src)
            moved.append((src, dst))
    except OSError as exc:
        for src, dst in reversed(moved):
            try:
                src.rename(dst)
            except OSError:
                pass
        raise RuntimeError(f"Erreur lors de l'annulation : {exc}") from exc

    dest_dirs = {dst.parent for _, dst in pairs}
    for d in sorted(dest_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def execute_rename(pairs: list[tuple[Path, Path]]) -> None:
    """
    Execute rename pairs atomically: pre-check all destinations, then move.
    Rolls back on error. Removes empty source directories afterwards.
    """
    for src, dst in pairs:
        if dst.exists():
            raise FileExistsError(f"Le fichier destination existe déjà : {dst.name}")

    moved: list[tuple[Path, Path]] = []
    try:
        for src, dst in pairs:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            moved.append((src, dst))
    except OSError as exc:
        for src, dst in reversed(moved):
            try:
                dst.rename(src)
            except OSError:
                pass
        raise RuntimeError(f"Erreur lors du renommage : {exc}") from exc

    source_dirs = {src.parent for src, _ in pairs}
    for d in sorted(source_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
