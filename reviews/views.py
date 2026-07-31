from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from shop.models import Product

from .forms import ProductReviewForm, ReviewReportForm
from .models import ProductReview, Review, ReviewReport


def create_review(request, product_id):
    return redirect('reviews:create_product_review', product_id=product_id)


def _approved_reviews(product):
    return ProductReview.objects.filter(
        product=product,
        status=ProductReview.Status.APPROVED,
    ).select_related('reviewer')


def product_review_list(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = _approved_reviews(product).prefetch_related('helpful_votes')
    paginator = Paginator(reviews, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    from django.db.models import Avg
    overall = reviews.aggregate(avg_rating=Avg('overall_rating'), total=Count('id'))

    context = {
        'product': product,
        'page_obj': page_obj,
        'reviews': page_obj.object_list,
        'average': round(overall['avg_rating'], 1) if overall['avg_rating'] else 0,
        'total': overall['total'],
        'recommend_pct': _recommend_percent(reviews),
    }
    return render(request, 'reviews/product_review_list.html', context)


def _recommend_percent(reviews):
    total = reviews.count()
    if not total:
        return 0
    recommended = reviews.filter(recommendation_rating__gte=70).count()
    return round(recommended / total * 100)


@login_required
def create_product_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    existing = ProductReview.objects.filter(product=product, reviewer=request.user).first()
    if existing:
        messages.warning(request, 'You have already reviewed this product. You can edit your review below.')
        return redirect('reviews:product_review_detail', review_id=existing.pk)

    if request.method == 'POST':
        form = ProductReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.reviewer = request.user
            review.save()
            messages.success(request, 'Thanks for your detailed review!')
            return redirect('reviews:product_review_detail', review_id=review.pk)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductReviewForm()

    context = {'product': product, 'form': form}
    return render(request, 'reviews/product_review_form.html', context)


@login_required
def edit_product_review(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id)
    if review.reviewer != request.user and not request.user.is_staff:
        raise PermissionError
    if request.method == 'POST':
        form = ProductReviewForm(request.POST, request.FILES, instance=review)
        if form.is_valid():
            review = form.save()
            messages.success(request, 'Your review has been updated.')
            return redirect('reviews:product_review_detail', review_id=review.pk)
    else:
        form = ProductReviewForm(instance=review)
    context = {'product': review.product, 'form': form, 'review': review, 'editing': True}
    return render(request, 'reviews/product_review_form.html', context)


def product_review_detail(request, review_id):
    review = get_object_or_404(
        ProductReview.objects.select_related('reviewer', 'product'),
        pk=review_id,
    )
    if not review.is_approved and not (request.user.is_staff or request.user == review.reviewer):
        from django.http import Http404
        raise Http404
    context = {
        'review': review,
        'is_helpful': review.helpful_votes.filter(pk=request.user.pk).exists() if request.user.is_authenticated else False,
    }
    return render(request, 'reviews/product_review_detail.html', context)


@login_required
@require_POST
def toggle_review_helpful(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id)
    if request.user in review.helpful_votes.all():
        review.helpful_votes.remove(request.user)
    else:
        review.helpful_votes.add(request.user)
    return redirect('reviews:product_review_detail', review_id=review.pk)


@login_required
def report_review(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id)
    if request.method == 'POST':
        form = ReviewReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.review = review
            report.reporter = request.user
            report.save()
            messages.success(request, 'Thanks — our team will look into this review.')
            return redirect('reviews:product_review_detail', review_id=review.pk)
    else:
        form = ReviewReportForm()
    context = {'review': review, 'form': form}
    return render(request, 'reviews/report_review.html', context)
