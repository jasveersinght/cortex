def mock_content(payload: dict) -> dict:
    audience = payload.get("target_audience", "target audience")
    product = payload.get("product", "insurance")
    return {
        "campaign": {"title": "Protect Tomorrow, Today", "objective": payload.get("campaign_goal", "Awareness"), "audience": audience},
        "messaging": {"core_message": f"Make informed {product} decisions before they become urgent.", "angle": "Future-focused protection", "hook": "Your future deserves more than a promise."},
        "linkedin": {"hook": "Your future deserves more than a promise.", "body": f"Planning for {product.lower()} is part of planning for the future. Start with the right questions, understand your needs, and make an informed decision.", "cta": "Explore your options."},
        "instagram": {"caption": "Plan today for the life you are building tomorrow.", "carousel": ["YOUR FUTURE NEEDS A PLAN.", "Understand your needs.", "Make an informed choice.", "Protect what matters.", "Start today."], "cta": "Learn more"},
        "x": {"post": "Planning for the future is not about expecting the worst. It is about being prepared for what matters."},
        "ab_variants": [
            {"name": "A", "angle": "Emotional", "hook": "What are you building your future for?", "message": "Protect the people and goals that matter."},
            {"name": "B", "angle": "Financial planning", "hook": "Your income supports more than today.", "message": "Think about protection as part of your wider financial plan."},
            {"name": "C", "angle": "Aspirational", "hook": "Build the future. Plan for it too.", "message": "Turn future goals into informed decisions today."}
        ],
        "visual": {
            "concept": "Young professional reviewing a financial plan with family context",
            "composition": "Subject on right, clean headline area on left",
            "mood": "Premium, trustworthy, optimistic",
            "headline": f"Protect Tomorrow, Today — {product}",
            "cta": "Plan your protection",
            "image_url": f"https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80"
        },
        "reel": {"duration_seconds": 8, "hook": "You plan your future. Do you plan for protecting it?", "scenes": [{"time": "0-2s", "visual": "Young professional at a desk", "on_screen_text": "You plan your future."}, {"time": "2-5s", "visual": "Reviewing a financial plan", "on_screen_text": "Plan for what matters."}, {"time": "5-8s", "visual": "Warm family moment", "on_screen_text": "Protect Tomorrow, Today."}], "cta": "Learn more"},
        "video_prompt": "Vertical premium insurance commercial, young Indian professional reviewing a financial plan in a modern office, subtle transition to a warm family moment, realistic cinematic lighting, smooth camera movement, trustworthy optimistic mood, clean composition, 9:16 social media reel, no visible text, no watermark"
    }
