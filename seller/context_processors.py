from django.core.exceptions import ObjectDoesNotExist

def search_action_context(request):
    path = request.path

    if "best-sellers" in path:
        return {"search_action": "seller:best_sellers"}
    return {
        "search_action": "seller:sellers_profile_search"
    }

def seller_context(request):
    context = {"is_seller": False, "seller_profile": None}
    if request.user.is_authenticated:
        try:
            profile = request.user.sellerprofile
            context["is_seller"] = True
            context["seller_profile"] = profile
        except ObjectDoesNotExist:
            pass
    return context
