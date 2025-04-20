from django.shortcuts import render, get_object_or_404 , redirect
from cart.forms import CartAddProductForm
from .models import Category, Product
from django.core.paginator import Paginator
from django.db.models import Q


# from django.views import generic

# class IndexView(generic.ListView):
#     template_name = 'shop/index.html'
#     context_object_name = 'products'

#     def get_queryset(self):
#         '''Return five lattest products
#         '''
#         return Product.objects.filter(created__lte=timezone.now()
#         ).order_by('-created')[:5]



# def product_list(request, category_slug=None):
#     category = None
#     categories = Category.objects.all()
#     products = Product.objects.filter(available=True)
#     if category_slug:
#         category = get_object_or_404(Category, slug=category_slug)
#         products = products.filter(category=category)
#     context = {'category': category, 'categories': categories, 'products': products}
#     return render(request, 'shop/product/list.html', context)

# def product_list(request, category_slug=None):
#     category = None
#     categories = Category.objects.all()
#     # products = Product.objects.all()
#     Product.objects.filter(available=True)


#     if category_slug:
#         category = get_object_or_404(Category, slug=category_slug)
#         products = products.filter(category=category)

#     paginator = Paginator(products, 9)  # Show 9 products per page
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)

#     return render(request, 'shop/product/list.html', {
#         'category': category,
#         'categories': categories,
#         'products': page_obj,  # Pass paginated products
#         'page_obj': page_obj,  # Optional for easier template logic
#     })



def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=category, available=True)
    else:
        products = Product.objects.filter(available=True)

    paginator = Paginator(products, 9)  # 9 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'shop/product/list.html', {
        'category': category,
        'categories': categories,
        'products': page_obj,
    })



# class ProductListView(generic.ListView):
#     template_name = 'shop/product/list.html'

#     def get_queryset(self):
#         return Product.objects.filter(available=True)

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         category = None
#         if category_slug:
#             category = get_object_or_404(Category, slug=category_slug)
#         context['category'] = category
#         context['categories'] = Category.objects.all()





def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    cart_product_form = CartAddProductForm()
    context = {'product': product, 'cart_product_form': cart_product_form}
    return render(request, 'shop/product/detail.html', context)


# class ProductDetialView(generic.DetailView):

#     template_name = 'shop/product/detail.html'
#     model = Product
#     form_class = CartAddProductForm

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['products'] = get_object_or_404(Product, 
#         id=id, slug=slug, available=True)
#         return context


def product_search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    products = Product.objects.all()
    product_categories = Category.objects.all()
    if category_slug:
        products = products.filter(category__slug=category_slug)

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    return render(request, "shop/product/product_search.html", {
        "results": products,
        "query": query,
        "selected_category": category_slug,
        "product_categories": product_categories,
        "search_action": "shop:product_search",  # optional, for your navbar
    })
  
