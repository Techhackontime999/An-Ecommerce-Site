# seller/context_processors.py

def search_action_context(request):
    path = request.path

    if "best-sellers" in path:
        return {"search_action": "seller:best_sellers"}
    return {
        
        "search_action": "seller:sellers_profile_search"
    }
