"""Business math for one store-day, kept apart from the API and storage code."""


def calculate_restaurant_metrics(gross_sales: float, labor_cost: float, labor_hours: float) -> dict:
    """CPLH (cost per labor hour) and labor % of sales, rounded to cents.
    A metric whose denominator is zero is None: undefined, not zero."""
    cplh = round(labor_cost / labor_hours, 2) if labor_hours > 0 else None
    labor_pct = round(labor_cost / gross_sales * 100, 2) if gross_sales > 0 else None
    return {"cplh": cplh, "labor_pct": labor_pct}


def is_over_threshold(metrics: dict, threshold_pct: float) -> bool:
    return metrics["labor_pct"] is not None and metrics["labor_pct"] > threshold_pct
