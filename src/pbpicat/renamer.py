import re
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


def find_max_number(dest_dir: Path, basename: str, extensions: set[str] | None = None) -> int:
    """Return the maximum numeric suffix used in dest_dir for filenames containing basename_NNN.

    If extensions is given, only files whose suffix (lowercased) is in that set are considered.
    """
    if basename:
        pattern = re.compile(rf"(?:^|_){re.escape(basename)}_(\d+)", re.IGNORECASE)
    else:
        pattern = re.compile(r"(?:^|_)(\d+)(?:$|\.[^.]+$|_)", re.IGNORECASE)
    max_num = 0
    if dest_dir.exists():
        for f in dest_dir.iterdir():
            if extensions is not None and f.suffix.lower() not in extensions:
                continue
            m = pattern.search(f.name)
            if m:
                max_num = max(max_num, int(m.group(1)))
    return max_num


def build_rename_plan(
    dest_root: str,
    schema_fields: list[str],
    source_paths: list[Path],
    sidecar_extensions: list[str],
    image_extensions: list[str],
    video_extensions: list[str] | None = None,
    video_marker: str = "",
    video_marker_pos: int = 0,
) -> list[tuple[Path, Path]]:
    """
    Build (src, dst) pairs for source_paths and their sidecars.
    Raises ValueError for schema errors, FileExistsError if a destination already exists.

    For video files, video_marker is inserted at video_marker_pos within the schema parts.
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

    next_img_num = 0
    next_vid_num = 0
    min_digits = 0
    if numeric_spec:
        min_digits = len(numeric_spec)
        next_img_num = find_max_number(dest_subdir, basename, img_exts) + 1
        next_vid_num = find_max_number(dest_subdir, video_basename, video_exts) + 1

    for src in source_paths:
        is_video = src.suffix.lower() in video_exts

        if numeric_spec:
            if is_video:
                num_str = str(next_vid_num).zfill(min_digits)
                next_vid_num += 1
            else:
                num_str = str(next_img_num).zfill(min_digits)
                next_img_num += 1
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
