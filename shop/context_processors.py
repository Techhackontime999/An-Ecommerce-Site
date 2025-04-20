# shop/context_processors.py

def search_action_context(request):
    return {
        "search_action": "shop:product_search"
    }
