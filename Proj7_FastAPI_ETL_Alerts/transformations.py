def calculate_restaurant_metrics(gross_sales: float, labor_cost: float, labor_hours: float) -> dict:
    """
    Transforms raw POS and scheduling data into actionable business metrics.
    Returns a dictionary with CPLH and Labor Percentage.
    """
    # Prevent division by zero errors
    if labor_hours <= 0 or gross_sales <= 0:
        return {
            "cplh": 0.0,
            "labor_pct": 0.0
        }

    # The Core Business Math
    cplh = round(labor_cost / labor_hours, 2)
    labor_pct = round((labor_cost / gross_sales) * 100, 2)

    return {
        "cplh": cplh,
        "labor_pct": labor_pct
    }