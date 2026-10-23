from app.services.version_matcher import match_nodes
class Old:
    def __init__(self,id,logical_id,heading,level=1):
        self.id=id; self.logical_id=logical_id; self.heading=heading; self.level=level
class Parsed:
    def __init__(self,key,heading,level=1):
        self.logical_key=key; self.heading=heading; self.level=level
def test_unique_same_heading_matches_logical_identity():
    old=[Old("old1","logical1","1.1 Intended Use")]
    parsed=[Parsed("newkey","1.1 Intended Use")]
    assert match_nodes(old,parsed)[0][1]=="logical1"
def test_ambiguous_heading_is_not_confidently_matched():
    old=[Old("old1","l1","1.1 General"),Old("old2","l2","2.1 General")]
    parsed=[Parsed("new","3.1 General")]
    assert match_nodes(old,parsed)[0][1] is None
