"""Tests unitaires pour src/renamer.py (sans dépendance Qt)."""

from pathlib import Path

import pytest

from pbpicat.renamer import build_rename_plan, execute_rename, find_max_number, undo_rename, validate_schema

# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------


def test_schema_simple():
    dirs, parts, num = validate_schema(["abc", "def", "", "ghi", "", ""])
    assert dirs == ["abc", "def", "ghi"]
    assert parts == ["abc", "def", "ghi"]
    assert num is None


def test_schema_with_numeric():
    dirs, parts, num = validate_schema(["abc", "def", "", "ghi", "", "###"])
    assert dirs == ["abc", "def", "ghi"]
    assert parts == ["abc", "def", "ghi"]
    assert num == "###"


def test_schema_two_numerics_raises():
    with pytest.raises(ValueError, match="plusieurs zones numériques"):
        validate_schema(["abc", "def", "#", "ghi", "", "###"])


def test_schema_underscore_raises():
    with pytest.raises(ValueError, match="_"):
        validate_schema(["abc_bad", "def"])


def test_schema_dot_raises():
    with pytest.raises(ValueError, match=r"\."):
        validate_schema(["abc.bad", "def"])


def test_schema_empty_raises():
    with pytest.raises(ValueError, match="vide"):
        validate_schema(["", "", "", "", "", ""])


def test_schema_numeric_only():
    dirs, parts, num = validate_schema(["###", "", "", "", "", ""])
    assert dirs == []
    assert parts == []
    assert num == "###"


# ---------------------------------------------------------------------------
# find_max_number
# ---------------------------------------------------------------------------


def test_find_max_number_numeric_order(tmp_path):
    prefix = "abc_def"
    for name in ["abc_def_1.jpg", "abc_def_13.jpg", "abc_def_101.jpg", "abc_def_121.jpg", "abc_def_2.jpg"]:
        (tmp_path / name).touch()
    assert find_max_number(tmp_path, prefix) == 121


def test_find_max_number_empty_dir(tmp_path):
    assert find_max_number(tmp_path, "abc") == 0


def test_find_max_number_no_match(tmp_path):
    (tmp_path / "other_001.jpg").touch()
    assert find_max_number(tmp_path, "abc") == 0


def test_find_max_number_empty_basename(tmp_path):
    for name in ["03.jpg", "07.jpg", "012.jpg"]:
        (tmp_path / name).touch()
    assert find_max_number(tmp_path, "") == 12


def test_find_max_number_extension_filter(tmp_path):
    (tmp_path / "abc_010.jpg").touch()
    (tmp_path / "abc_020.mp4").touch()
    assert find_max_number(tmp_path, "abc", {".jpg"}) == 10
    assert find_max_number(tmp_path, "abc", {".mp4"}) == 20
    assert find_max_number(tmp_path, "abc", {".png"}) == 0


# ---------------------------------------------------------------------------
# build_rename_plan
# ---------------------------------------------------------------------------


def test_build_plan_no_numeric(tmp_path):
    src = tmp_path / "img.jpg"
    src.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "def", "", "ghi", "", ""], [src], [], [".jpg"])
    assert len(plan) == 1
    src_p, dst_p = plan[0]
    assert dst_p == dest / "abc" / "def" / "ghi" / "abc_def_ghi.jpg"


def test_build_plan_with_sidecar(tmp_path):
    src = tmp_path / "img.jpg"
    sc = tmp_path / "img.xmp"
    src.touch()
    sc.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", ""], [src], [".xmp"], [".jpg"])
    assert len(plan) == 2
    exts = {p[1].suffix for p in plan}
    assert exts == {".jpg", ".xmp"}


def test_build_plan_numeric_counter(tmp_path):
    src1 = tmp_path / "img1.jpg"
    src2 = tmp_path / "img2.jpg"
    src1.touch()
    src2.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", "##"], [src1, src2], [], [".jpg"])
    names = [p[1].name for p in plan]
    assert "abc_01.jpg" in names
    assert "abc_02.jpg" in names


def test_build_plan_separate_counters_images_videos(tmp_path):
    img = tmp_path / "photo.jpg"
    vid = tmp_path / "clip.mp4"
    img.touch()
    vid.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", "##"], [img, vid], [], [".jpg"], [".mp4"])
    names = {p[1].name for p in plan}
    assert "abc_01.jpg" in names
    assert "abc_01.mp4" in names


def test_build_plan_separate_counters_continue_from_existing(tmp_path):
    img = tmp_path / "photo.jpg"
    vid = tmp_path / "clip.mp4"
    img.touch()
    vid.touch()
    dest = tmp_path / "dest"
    subdir = dest / "abc"
    subdir.mkdir(parents=True)
    (subdir / "abc_05.jpg").touch()
    (subdir / "abc_03.mp4").touch()
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", "##"], [img, vid], [], [".jpg"], [".mp4"])
    names = {p[1].name: p[1] for p in plan}
    assert "abc_06.jpg" in names
    assert "abc_04.mp4" in names


def test_build_plan_video_marker(tmp_path):
    img = tmp_path / "photo.jpg"
    vid = tmp_path / "clip.mp4"
    img.touch()
    vid.touch()
    dest = tmp_path / "dest"
    # marker "VID" at position 1 among parts ["abc", "def"] → vid stem = abc_VID_def
    plan = build_rename_plan(
        str(dest),
        ["abc", "def", "", "", "", ""],
        [img, vid],
        [],
        [".jpg"],
        [".mp4"],
        video_marker="VID",
        video_marker_pos=1,
    )
    names = {p[1].name for p in plan}
    assert "abc_def.jpg" in names
    assert "abc_VID_def.mp4" in names


def test_build_plan_extension_lowercased(tmp_path):
    src = tmp_path / "IMG_001.JPG"
    src.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", ""], [src], [], [".jpg"])
    assert plan[0][1].suffix == ".jpg"


def test_build_plan_sidecar_not_present(tmp_path):
    src = tmp_path / "img.jpg"
    src.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", ""], [src], [".xmp"], [".jpg"])
    assert len(plan) == 1


def test_build_plan_numeric_only_schema(tmp_path):
    src = tmp_path / "img.jpg"
    src.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(str(dest), ["##", "", "", "", "", ""], [src], [], [".jpg"])
    assert plan[0][1].name == "01.jpg"
    assert plan[0][1].parent == dest


def test_build_plan_video_marker_pos_beyond_end(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.touch()
    dest = tmp_path / "dest"
    plan = build_rename_plan(
        str(dest),
        ["abc", "", "", "", "", ""],
        [vid],
        [],
        [],
        [".mp4"],
        video_marker="VID",
        video_marker_pos=99,
    )
    assert plan[0][1].name == "abc_VID.mp4"


def test_build_plan_numeric_continues_from_max(tmp_path):
    src = tmp_path / "img.jpg"
    src.touch()
    dest = tmp_path / "dest"
    # dest_subdir = dest/abc (single non-empty non-numeric field)
    subdir = dest / "abc"
    subdir.mkdir(parents=True)
    (subdir / "abc_1002.jpg").touch()
    plan = build_rename_plan(str(dest), ["abc", "", "", "", "", "###"], [src], [], [".jpg"])
    assert plan[0][1].name == "abc_1003.jpg"


# ---------------------------------------------------------------------------
# execute_rename
# ---------------------------------------------------------------------------


def test_execute_rename_moves_files(tmp_path):
    src = tmp_path / "img.jpg"
    src.write_text("data")
    dst = tmp_path / "out" / "renamed.jpg"
    execute_rename([(src, dst)])
    assert dst.exists()
    assert not src.exists()


def test_execute_rename_removes_empty_source_dir(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    src = subdir / "img.jpg"
    src.write_text("data")
    dst = tmp_path / "out" / "renamed.jpg"
    execute_rename([(src, dst)])
    assert not subdir.exists()


def test_execute_rename_aborts_on_existing_dest(tmp_path):
    src = tmp_path / "img.jpg"
    src.write_text("data")
    dst = tmp_path / "renamed.jpg"
    dst.write_text("existing")
    with pytest.raises(FileExistsError):
        execute_rename([(src, dst)])
    assert src.exists()


def test_execute_rename_rollback_on_partial_failure(tmp_path):
    src1 = tmp_path / "a.jpg"
    src2 = tmp_path / "b.jpg"
    src1.write_text("a")
    src2.write_text("b")
    dst1 = tmp_path / "out" / "a_renamed.jpg"
    dst2 = tmp_path / "out" / "b_renamed.jpg"
    dst2.parent.mkdir()
    dst2.write_text("conflict")
    with pytest.raises(FileExistsError):
        execute_rename([(src1, dst1), (src2, dst2)])
    assert src1.exists()
    assert src2.exists()


def test_execute_rename_rollback_on_oserror(tmp_path):
    src1 = tmp_path / "a.jpg"
    src2 = tmp_path / "nonexistent.jpg"  # n'existe pas → OSError au 2e rename
    src1.write_text("a")
    dst1 = tmp_path / "out" / "a_renamed.jpg"
    dst2 = tmp_path / "out" / "b_renamed.jpg"
    with pytest.raises(RuntimeError):
        execute_rename([(src1, dst1), (src2, dst2)])
    assert src1.exists()
    assert not dst1.exists()


# ---------------------------------------------------------------------------
# undo_rename
# ---------------------------------------------------------------------------


def test_undo_rename_basic(tmp_path):
    src = tmp_path / "original" / "img.jpg"
    dst = tmp_path / "out" / "renamed.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("data")
    undo_rename([(src, dst)])
    assert src.exists()
    assert not dst.exists()
    assert not dst.parent.exists()


def test_undo_rename_missing_dst(tmp_path):
    src = tmp_path / "original.jpg"
    dst = tmp_path / "out" / "renamed.jpg"
    with pytest.raises(FileNotFoundError, match="introuvable"):
        undo_rename([(src, dst)])


def test_undo_rename_existing_src(tmp_path):
    src = tmp_path / "original.jpg"
    dst = tmp_path / "renamed.jpg"
    src.write_text("original")
    dst.write_text("renamed")
    with pytest.raises(FileExistsError, match="déjà présent"):
        undo_rename([(src, dst)])


def test_undo_rename_non_empty_dest_not_removed(tmp_path):
    src = tmp_path / "sub" / "img.jpg"
    dst = tmp_path / "out" / "renamed.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("data")
    (dst.parent / "other.jpg").write_text("keep")
    undo_rename([(src, dst)])
    assert src.exists()
    assert dst.parent.exists()


def test_undo_rename_oserror_rollback(tmp_path):
    src1 = tmp_path / "sub1" / "orig1.jpg"
    # Blocker est un fichier : mkdir("blocker") échoue → OSError
    blocker = tmp_path / "sub2"
    blocker.write_text("file, not dir")
    src2 = blocker / "orig2.jpg"
    dst1 = tmp_path / "out" / "dst1.jpg"
    dst2 = tmp_path / "out" / "dst2.jpg"
    dst1.parent.mkdir(parents=True)
    dst1.write_text("a")
    dst2.write_text("b")
    with pytest.raises(RuntimeError, match="Erreur lors de l'annulation"):
        undo_rename([(src1, dst1), (src2, dst2)])
    assert dst1.exists()  # rollback a restauré dst1


def test_undo_rename_rollback_inner_oserror(tmp_path, monkeypatch):
    """Couvre le except OSError silencieux dans la boucle de rollback d'undo_rename."""
    src1 = tmp_path / "sub1" / "orig1.jpg"
    src2 = tmp_path / "sub2" / "orig2.jpg"
    dst1 = tmp_path / "out" / "dst1.jpg"
    dst2 = tmp_path / "out" / "dst2.jpg"
    dst1.parent.mkdir(parents=True)
    dst1.write_text("a")
    dst2.write_text("b")

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise OSError("disk full")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError, match="annulation"):
        undo_rename([(src1, dst1), (src2, dst2)])


def test_undo_rename_dest_dir_rmdir_oserror(tmp_path, monkeypatch):
    """Couvre le except OSError silencieux dans le nettoyage du répertoire destination."""
    src = tmp_path / "sub" / "img.jpg"
    dst = tmp_path / "out" / "renamed.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("data")

    def mock_rmdir(self):
        raise OSError("busy")

    monkeypatch.setattr(Path, "rmdir", mock_rmdir)
    undo_rename([(src, dst)])  # ne doit pas lever d'exception malgré rmdir raté
    assert src.exists()


def test_execute_rename_rollback_inner_oserror(tmp_path, monkeypatch):
    """Couvre le except OSError silencieux dans la boucle de rollback d'execute_rename."""
    src1 = tmp_path / "a.jpg"
    src2 = tmp_path / "b.jpg"
    src1.write_text("a")
    src2.write_text("b")
    dst1 = tmp_path / "out" / "a.jpg"
    dst2 = tmp_path / "out" / "b.jpg"

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise OSError("disk full")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_rename([(src1, dst1), (src2, dst2)])


def test_execute_rename_source_dir_rmdir_oserror(tmp_path, monkeypatch):
    """Couvre le except OSError silencieux dans le nettoyage du répertoire source."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    src = subdir / "img.jpg"
    src.write_text("data")
    dst = tmp_path / "out" / "renamed.jpg"

    def mock_rmdir(self):
        raise OSError("busy")

    monkeypatch.setattr(Path, "rmdir", mock_rmdir)
    execute_rename([(src, dst)])  # ne doit pas lever d'exception malgré rmdir raté
    assert dst.exists()
