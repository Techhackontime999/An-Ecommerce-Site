# from django.shortcuts import render
# from django.db.models import Q

# from shop.models import Product, Category
# # from about.models import TeamMember
# # from about.models import TeamMember, Mission, Story  # optional

# def global_search(request):
#     query = request.GET.get('q', '').strip()
#     category_slug = request.GET.get('category', '').strip()
    
#     results = {}
    
#     # Product filtering
#     products = Product.objects.all()
#     if category_slug:
#         products = products.filter(category__slug=category_slug)

#     if query:
#         results["products"] = products.filter(
#             Q(name__icontains=query) | Q(description__icontains=query)
#         )
#     else:
#         results["products"] = products



#     # Deal search (by product's name/description)
#     # results["deals"] = Deal.objects.filter(
#     #     Q(product__name__icontains=query) | Q(product__description__icontains=query)
#     # ) if query else []


#     # Optional: About 
#     results["team"] = TeamMember.objects.filter(name__icontains=query) if query else []
  

#     return render(request, "search/global_search.html", {
#         "query": query,
#         "results": results,
#         "selected_category": category_slug,
#     })


