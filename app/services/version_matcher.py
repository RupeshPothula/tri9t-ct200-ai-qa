from .tree_builder import norm, digest
def match_nodes(old_nodes, parsed_nodes):
    """Match by stable printed section number + normalized heading; fall back to unique heading.
    Ambiguous candidates are not matched. Hashes are content fingerprints, not semantic equivalence.
    """
    old_by_key={}
    for n in old_nodes:
        old_by_key.setdefault((n.heading.split(" ",1)[0] if n.level else "title",norm(n.heading)),[]).append(n)
    results=[]
    used=set()
    for p in parsed_nodes:
        num=p.heading.split(" ",1)[0] if p.level else "title"
        candidates=old_by_key.get((num,norm(p.heading)),[])
        if len(candidates)==1 and candidates[0].id not in used:
            match=candidates[0]; used.add(match.id); results.append((p,match.logical_id))
        else:
            # same heading fallback only if unique in each version
            candidates=[n for n in old_nodes if norm(n.heading)==norm(p.heading) and n.id not in used]
            results.append((p,candidates[0].logical_id if len(candidates)==1 else None))
    return results
