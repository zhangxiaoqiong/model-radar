from datetime import date
from scripts.run_sync import matching_openrouter, recent_mainstream_aa

def test_scope_is_mainstream_and_recent():
    rows=[
        {"name":"New Model","slug":"new-model","release_date":"2026-09-01","model_creator":{"name":"OpenAI"}},
        {"name":"Old Model","slug":"old-model","release_date":"2025-01-01","model_creator":{"name":"OpenAI"}},
        {"name":"Niche Model","slug":"niche","release_date":"2026-09-01","model_creator":{"name":"Small Lab"}},
    ]
    selected=recent_mainstream_aa(rows,today=date(2026,9,23))
    assert [row["slug"] for row in selected]==["new-model"]
    router=[
        {"id":"openai/new-model","name":"OpenAI: New Model"},
        {"id":"small/niche","name":"Small: Niche Model"},
    ]
    assert [row["id"] for row in matching_openrouter(router,selected)]==["openai/new-model"]
