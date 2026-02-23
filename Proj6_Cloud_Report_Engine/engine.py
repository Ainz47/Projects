def calculate_dominance(quiz_data: dict) -> dict:
    """Calculates the normalized score, assigns a tier, and identifies growth leaks."""
    
    # Calculate Total (Assuming max possible is 100 for this MVP)
    scores = quiz_data["scores"]
    total_score = sum(scores.values())
    
    # Tier Assignment Logic
    if total_score >= 80:
        tier = "Dominant"
    elif total_score >= 50:
        tier = "Contender"
    else:
        tier = "Beginner"
        
    # Diagnostic Rules Engine
    leaks = []
    if scores.get("local_seo", 0) < 15:
        leaks.append("SEO Warning: Low organic visibility. Competitors own the Maps pack.")
    if scores.get("paid_ads", 0) < 15:
        leaks.append("Ad Leak: Your ad spend is bleeding due to poor targeting.")
    if scores.get("reputation", 0) < 20:
        leaks.append("Trust Gap: Missing automated systems to capture 5-star reviews.")

    return {
        "final_score": total_score,
        "tier": tier,
        "growth_leaks": leaks
    }