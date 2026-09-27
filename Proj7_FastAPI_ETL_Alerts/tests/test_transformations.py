from transformations import calculate_restaurant_metrics, is_over_threshold


def test_cplh_and_labor_pct():
    assert calculate_restaurant_metrics(5000, 1500, 75) == {"cplh": 20.0, "labor_pct": 30.0}


def test_rounds_to_cents():
    assert calculate_restaurant_metrics(3000, 1000, 30) == {"cplh": 33.33, "labor_pct": 33.33}


def test_zero_sales_leaves_labor_pct_undefined_not_zero():
    # $800 of labor on a day with no sales is not "0% labor".
    assert calculate_restaurant_metrics(0, 800, 40) == {"cplh": 20.0, "labor_pct": None}


def test_zero_hours_leaves_cplh_undefined():
    assert calculate_restaurant_metrics(5000, 0, 0) == {"cplh": None, "labor_pct": 0.0}


def test_threshold_is_strictly_above():
    assert is_over_threshold({"labor_pct": 25.01}, 25.0)
    assert not is_over_threshold({"labor_pct": 25.0}, 25.0)


def test_undefined_labor_pct_never_alerts():
    assert not is_over_threshold({"labor_pct": None}, 25.0)
