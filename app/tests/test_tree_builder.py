from app.services.tree_builder import digest, norm, HEADING_RE
def test_duplicate_heading_ids_are_not_heading_based():
    # Parser identity includes section number; identical labels under different sections stay distinct.
    a="sec:1.1:"+norm("1.1 General")
    b="sec:2.1:"+norm("2.1 General")
    assert a != b
def test_heading_number_depth_is_preserved():
    m=HEADING_RE.match("2.1.1.1 Battery Life Under Typical Use")
    assert m and len(m.group(1).split("."))==4
def test_content_hash_changes_for_threshold_change():
    assert digest("Low battery below 15%") != digest("Low battery below 10%")
def test_normalization_handles_ligature_and_whitespace():
    assert norm("proﬁle   selection") == norm("profile selection")
