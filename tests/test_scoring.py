from dqs.scoring import range_score


def test_range_score_boundary_goes_higher():
    payload={"forecast":{"range_probabilities":[
        {"lower":82000,"upper":84000,"probability":0.45,"label":"82-84"},
        {"lower":84000,"upper":86000,"probability":0.55,"label":"84-86"}
    ]}}
    result=range_score(payload,84000)
    assert result["exact_primary"] is True
    assert result["actual_bracket"]["lower"] == 84000
