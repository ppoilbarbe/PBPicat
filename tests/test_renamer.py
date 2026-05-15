"""Tests unitaires pour src/renamer.py (sans dépendance Qt)."""

from pathlib import Path

import pytest

from pbpicat.renamer import (
    build_rename_plan,
    build_renumber_plan,
    execute_rename,
    execute_renumber,
    find_max_number,
    undo_rename,
    undo_renumber,
    validate_schema,
)

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


# ---------------------------------------------------------------------------
# build_renumber_plan
# ---------------------------------------------------------------------------


def test_renumber_plan_no_numeric_raises(tmp_path):
    src = tmp_path / "abc_def.jpg"
    src.touch()
    with pytest.raises(ValueError, match="numérique"):
        build_renumber_plan(["abc", "def", "", "", "", ""], [src], [], [".jpg"])


def test_renumber_plan_empty_list():
    plan = build_renumber_plan(["abc", "", "", "", "", "##"], [], [], [".jpg"])
    assert plan == []


def test_renumber_plan_already_correct(tmp_path):
    """Fichiers déjà numérotés depuis 1 sans trous → plan vide."""
    f1 = tmp_path / "abc_01.jpg"
    f2 = tmp_path / "abc_02.jpg"
    f1.touch()
    f2.touch()
    plan = build_renumber_plan(["abc", "", "", "", "", "##"], [f1, f2], [], [".jpg"])
    assert plan == []


def test_renumber_plan_fills_gaps(tmp_path):
    """Trous dans la numérotation : 001, 003, 005 → 001, 002, 003."""
    f1 = tmp_path / "abc_001.jpg"
    f3 = tmp_path / "abc_003.jpg"
    f5 = tmp_path / "abc_005.jpg"
    f1.touch()
    f3.touch()
    f5.touch()
    plan = build_renumber_plan(["abc", "", "", "", "", "###"], [f1, f3, f5], [], [".jpg"])
    # f1 (001→001) est un no-op, exclu du plan
    assert len(plan) == 2
    src_to_dst = {src.name: dst.name for src, dst in plan}
    assert src_to_dst["abc_003.jpg"] == "abc_002.jpg"
    assert src_to_dst["abc_005.jpg"] == "abc_003.jpg"
    assert "abc_001.jpg" not in src_to_dst


def test_renumber_plan_circular_conflict_structure(tmp_path):
    """
    002, 003 → 001, 002 : la destination 002 du second fichier est la source du premier.
    Le plan doit inclure les deux paires (le conflit est résolu par execute_renumber).
    """
    f2 = tmp_path / "abc_002.jpg"
    f3 = tmp_path / "abc_003.jpg"
    f2.touch()
    f3.touch()
    plan = build_renumber_plan(["abc", "", "", "", "", "###"], [f2, f3], [], [".jpg"])
    srcs = {src.name for src, _ in plan}
    dsts = {dst.name for _, dst in plan}
    assert srcs == {"abc_002.jpg", "abc_003.jpg"}
    assert dsts == {"abc_001.jpg", "abc_002.jpg"}


def test_renumber_plan_separate_counters(tmp_path):
    """Images et vidéos ont des compteurs séparés démarrant à 1."""
    img1 = tmp_path / "x_003.jpg"
    img2 = tmp_path / "x_007.jpg"
    vid1 = tmp_path / "x_005.mp4"
    img1.touch()
    img2.touch()
    vid1.touch()
    plan = build_renumber_plan(
        ["x", "", "", "", "", "###"],
        [img1, vid1, img2],
        [],
        [".jpg"],
        [".mp4"],
    )
    dsts = {dst.name for _, dst in plan}
    assert "x_001.jpg" in dsts
    assert "x_002.jpg" in dsts
    assert "x_001.mp4" in dsts


def test_renumber_plan_includes_sidecars(tmp_path):
    """Les sidecars sont inclus dans le plan."""
    f3 = tmp_path / "abc_003.jpg"
    sc3 = tmp_path / "abc_003.xmp"
    f3.touch()
    sc3.touch()
    plan = build_renumber_plan(["abc", "", "", "", "", "###"], [f3], [".xmp"], [".jpg"])
    dsts = {dst.name for _, dst in plan}
    assert "abc_001.jpg" in dsts
    assert "abc_001.xmp" in dsts


def test_renumber_plan_multidot_sidecar(tmp_path):
    """Extensions sidecar multi-points correctement traitées."""
    f3 = tmp_path / "abc_003.jpg"
    sc3 = tmp_path / "abc_003.prompt.txt"
    f3.touch()
    sc3.touch()
    plan = build_renumber_plan(["abc", "", "", "", "", "###"], [f3], [".prompt.txt"], [".jpg"])
    dsts = {dst.name for _, dst in plan}
    assert "abc_001.prompt.txt" in dsts


def test_renumber_plan_sidecar_no_op_excluded(tmp_path):
    """Sidecar déjà au bon nom exclu du plan."""
    f2 = tmp_path / "abc_002.jpg"
    sc2 = tmp_path / "abc_002.xmp"
    f2.touch()
    sc2.touch()
    # Renumérotation donne 001 au premier fichier : f2→abc_001, sc2→abc_001.xmp
    plan = build_renumber_plan(["abc", "", "", "", "", "###"], [f2], [".xmp"], [".jpg"])
    # f2 est à 002, cible est 001 → changement
    dsts = {dst.name for _, dst in plan}
    assert "abc_001.jpg" in dsts
    assert "abc_001.xmp" in dsts


def test_renumber_plan_video_marker(tmp_path):
    """Le marqueur vidéo est appliqué lors de la renumérotation."""
    vid = tmp_path / "abc_VID_003.mp4"
    vid.touch()
    plan = build_renumber_plan(
        ["abc", "", "", "", "", "###"],
        [vid],
        [],
        [],
        [".mp4"],
        video_marker="VID",
        video_marker_pos=1,
    )
    dsts = {dst.name for _, dst in plan}
    assert "abc_VID_001.mp4" in dsts


def test_renumber_plan_extension_lowercased(tmp_path):
    """L'extension de destination est mise en minuscules."""
    src = tmp_path / "ABC_003.JPG"
    src.touch()
    plan = build_renumber_plan(["ABC", "", "", "", "", "###"], [src], [], [".jpg"])
    _, dst = plan[0]
    assert dst.suffix == ".jpg"


def test_renumber_plan_numeric_only_schema(tmp_path):
    """Schéma purement numérique : stem = numéro seul."""
    f3 = tmp_path / "003.jpg"
    f3.touch()
    plan = build_renumber_plan(["###", "", "", "", "", ""], [f3], [], [".jpg"])
    _, dst = plan[0]
    assert dst.name == "001.jpg"


# ---------------------------------------------------------------------------
# execute_renumber
# ---------------------------------------------------------------------------


def test_execute_renumber_basic(tmp_path):
    src = tmp_path / "abc_002.jpg"
    src.write_text("data")
    dst = tmp_path / "abc_001.jpg"
    execute_renumber([(src, dst)])
    assert dst.read_text() == "data"
    assert not src.exists()


def test_execute_renumber_empty_plan(tmp_path):
    execute_renumber([])  # ne doit pas lever d'exception


def test_execute_renumber_circular_conflict(tmp_path):
    """
    Cas circulaire : abc_002 → abc_001, abc_003 → abc_002.
    Sans deux phases, abc_002 serait écrasé avant que son contenu soit sauvegardé.
    abc_002.jpg existe toujours après (c'est la destination de abc_003).
    """
    f2 = tmp_path / "abc_002.jpg"
    f3 = tmp_path / "abc_003.jpg"
    f2.write_text("two")
    f3.write_text("three")
    execute_renumber([(f2, tmp_path / "abc_001.jpg"), (f3, tmp_path / "abc_002.jpg")])
    assert (tmp_path / "abc_001.jpg").read_text() == "two"
    assert (tmp_path / "abc_002.jpg").read_text() == "three"
    assert not (tmp_path / "abc_003.jpg").exists()  # f3 déplacé vers abc_002


def test_execute_renumber_rollback_phase1(tmp_path, monkeypatch):
    """Erreur en phase 1 : les fichiers déjà renommés en tmp sont restaurés."""
    f1 = tmp_path / "abc_001.jpg"
    f2 = tmp_path / "abc_002.jpg"
    f1.write_text("one")
    f2.write_text("two")

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        if call_count[0] == 2:
            raise OSError("disk full")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_renumber([(f1, tmp_path / "abc_010.jpg"), (f2, tmp_path / "abc_011.jpg")])

    assert f1.exists()
    assert f2.exists()


def test_execute_renumber_rollback_phase2(tmp_path, monkeypatch):
    """Erreur en phase 2 : tous les fichiers sont restaurés à leur nom original."""
    f1 = tmp_path / "abc_002.jpg"
    f2 = tmp_path / "abc_003.jpg"
    f1.write_text("two")
    f2.write_text("three")

    phase1_done = [0]
    orig = Path.rename

    def mock_rename(self, target):
        # Laisser passer la phase 1 (2 appels), échouer au premier appel de phase 2
        phase1_done[0] += 1
        if phase1_done[0] == 3:
            raise OSError("disk full")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_renumber([(f1, tmp_path / "abc_001.jpg"), (f2, tmp_path / "abc_002.jpg")])

    assert f1.exists()
    assert f2.exists()
    assert f1.read_text() == "two"
    assert f2.read_text() == "three"


# ---------------------------------------------------------------------------
# undo_renumber
# ---------------------------------------------------------------------------


def test_undo_renumber_basic(tmp_path):
    """Annulation simple : les fichiers retrouvent leur nom d'origine."""
    original = tmp_path / "abc_003.jpg"
    renamed = tmp_path / "abc_001.jpg"
    renamed.write_text("data")
    undo_renumber([(original, renamed)])
    assert original.read_text() == "data"
    assert not renamed.exists()


def test_undo_renumber_circular_conflict(tmp_path):
    """
    Cas qui provoquait le bug : après renumérotation 003,005 → 001,002,
    l'annulation veut faire 001→003 et 002→005, mais abc_003 est aussi une cible
    de la première paire → conflit circulaire résolu par undo_renumber.
    """
    # Situation après renumérotation de abc_003.jpg, abc_005.jpg → abc_001.jpg, abc_002.jpg
    new1 = tmp_path / "abc_001.jpg"
    new2 = tmp_path / "abc_002.jpg"
    new1.write_text("three")
    new2.write_text("five")

    original1 = tmp_path / "abc_003.jpg"  # nom d'origine de new1
    original2 = tmp_path / "abc_005.jpg"  # nom d'origine de new2

    # plan stocké lors de la renumérotation : (original, renamed)
    undo_renumber([(original1, new1), (original2, new2)])

    assert original1.read_text() == "three"
    assert original2.read_text() == "five"
    assert not new1.exists()
    assert not new2.exists()


def test_undo_renumber_with_sidecar(tmp_path):
    """L'annulation restaure aussi les sidecars."""
    orig_img = tmp_path / "abc_003.jpg"
    orig_sc = tmp_path / "abc_003.xmp"
    new_img = tmp_path / "abc_001.jpg"
    new_sc = tmp_path / "abc_001.xmp"
    new_img.write_text("img")
    new_sc.write_text("xmp")

    undo_renumber([(orig_img, new_img), (orig_sc, new_sc)])

    assert orig_img.read_text() == "img"
    assert orig_sc.read_text() == "xmp"
    assert not new_img.exists()
    assert not new_sc.exists()


def test_undo_renumber_missing_file_raises(tmp_path):
    """Fichier à annuler inexistant → RuntimeError."""
    orig = tmp_path / "abc_003.jpg"
    renamed = tmp_path / "abc_001.jpg"
    # renamed n'existe pas
    with pytest.raises(RuntimeError):
        undo_renumber([(orig, renamed)])


# ---------------------------------------------------------------------------
# execute_renumber — branches except OSError silencieux dans les rollbacks
# ---------------------------------------------------------------------------


def test_execute_renumber_rollback_phase1_inner_oserror(tmp_path, monkeypatch):
    """Couvre lignes 213-214 : rollback phase 1 (tmp→src) lève OSError, ignoré."""
    f1 = tmp_path / "abc_002.jpg"
    f2 = tmp_path / "abc_003.jpg"
    f1.write_text("two")
    f2.write_text("three")

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        # appel 1 : f1→tmp1 (succès)
        # appel 2 : f2→tmp2 (échec → rollback phase 1)
        # appel 3 : rollback tmp1→f1 (échec → lignes 213-214)
        if call_count[0] in (2, 3):
            raise OSError("simulated")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_renumber([(f1, tmp_path / "abc_001.jpg"), (f2, tmp_path / "abc_002.jpg")])


def test_execute_renumber_rollback_phase2_done2_oserror(tmp_path, monkeypatch):
    """Couvre lignes 224-227 : rollback done2 (dst→tmp) lève OSError, ignoré."""
    f1 = tmp_path / "abc_002.jpg"
    f2 = tmp_path / "abc_003.jpg"
    f1.write_text("two")
    f2.write_text("three")

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        # appels 1,2 : phase 1 (succès)
        # appel 3 : tmp1→dst1 (phase 2, succès → done2 a 1 entrée)
        # appel 4 : tmp2→dst2 (phase 2, échec → rollback phase 2)
        # appel 5 : rollback dst1→tmp1 (échec → lignes 224-227)
        if call_count[0] in (4, 5):
            raise OSError("simulated")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_renumber([(f1, tmp_path / "abc_001.jpg"), (f2, tmp_path / "abc_002.jpg")])


def test_execute_renumber_rollback_phase2_tmp_oserror(tmp_path, monkeypatch):
    """Couvre lignes 231-232 : rollback tmps→srcs lève OSError, ignoré."""
    f1 = tmp_path / "abc_002.jpg"
    f2 = tmp_path / "abc_003.jpg"
    f1.write_text("two")
    f2.write_text("three")

    call_count = [0]
    orig = Path.rename

    def mock_rename(self, target):
        call_count[0] += 1
        # appels 1,2 : phase 1 (succès)
        # appel 3 : tmp1→dst1 (phase 2, échec → done2 vide, 1er rollback ignoré)
        # appels 4,5 : rollback tmps→srcs (échec → lignes 231-232)
        if call_count[0] >= 3:
            raise OSError("simulated")
        return orig(self, target)

    monkeypatch.setattr(Path, "rename", mock_rename)
    with pytest.raises(RuntimeError):
        execute_renumber([(f1, tmp_path / "abc_001.jpg"), (f2, tmp_path / "abc_002.jpg")])
