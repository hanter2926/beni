from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from products.models import Product
from products.services import (
    eligible_shop_verifications,
    is_product_marketable,
    marketable_products,
)

from .categories import CATEGORIES, CATEGORIES_BY_SLUG
from .forms import (
    ContentReportForm,
    RepairAnswerForm,
    RepairGuideForm,
    RepairGuideResourceFormSet,
    RepairGuideStepFormSet,
    RepairQuestionForm,
)
from .models import (
    AnswerVote,
    ContentReport,
    QuestionVote,
    RepairAnswer,
    RepairGuide,
    RepairGuideCategory,
    RepairGuideResource,
    RepairQuestion,
)
from .permissions import can_contribute_guides, can_edit_guide
from .services import (
    ContentWorkflowError,
    moderate_answer,
    moderate_guide,
    moderate_question,
)


def _product_search(queryset, query):
    if not query:
        return queryset
    return queryset.filter(
        Q(name__icontains=query)
        | Q(description__icontains=query)
        | Q(category__icontains=query)
        | Q(shop__name__icontains=query)
    )


def _products_for_category(category):
    matches = Q()
    for term in (category['name'], *category['search_terms']):
        matches |= (
            Q(name__icontains=term)
            | Q(description__icontains=term)
            | Q(category__icontains=term)
        )
    return (
        marketable_products(
            Product.objects.filter(stock_quantity__gt=0).filter(matches)
        )
        .select_related('shop')
        .order_by('name', 'pk')
    )


def repair_guide_home(request):
    query = request.GET.get('q', '').strip()[:100]
    database_categories = RepairGuideCategory.objects.filter(
        is_active=True,
    ).prefetch_related('subcategories')
    category_by_slug = {category.slug: category for category in database_categories}
    categories = []
    for data in CATEGORIES:
        database_category = category_by_slug.get(data['slug'])
        category = _category_display_data(database_category, data)
        if not query or _category_matches(category, query):
            categories.append(category)
    known_slugs = {category['slug'] for category in categories}
    for database_category in database_categories:
        if database_category.slug in known_slugs:
            continue
        category = _category_display_data(database_category)
        if not query or _category_matches(category, query):
            categories.append(category)

    products = marketable_products(
        Product.objects.filter(stock_quantity__gt=0)
    ).select_related('shop')
    products = _product_search(products, query).order_by('-created_at', '-pk')
    page_obj = Paginator(products, 8).get_page(request.GET.get('page'))
    selected_category = request.GET.get('category', '').strip()[:80]
    selected_subcategory = request.GET.get('subcategory', '').strip()[:100]
    guides = _filter_guides(
        RepairGuide.objects.filter(status=RepairGuide.STATUS_PUBLISHED),
        request,
        query=query,
    )
    if selected_category:
        guides = guides.filter(category__slug=selected_category)
    if selected_subcategory:
        guides = guides.filter(
            subcategory__slug=selected_subcategory,
            subcategory__category__slug=selected_category,
        )
    guide_page = Paginator(guides, 8).get_page(request.GET.get('guide_page'))
    category_options = [
        _category_display_data(
            category_by_slug.get(data['slug']),
            data,
        )
        for data in CATEGORIES
    ]
    category_options.extend(
        _category_display_data(category)
        for category in database_categories
        if category.slug not in CATEGORIES_BY_SLUG
    )
    selected_category_model = category_by_slug.get(selected_category)
    return render(
        request,
        'repair_guides/home.html',
        {
            'categories': categories,
            'query': query,
            'products': page_obj.object_list,
            'page_obj': page_obj,
            'guides': guide_page.object_list,
            'guide_page': guide_page,
            'can_contribute': can_contribute_guides(request.user),
            'category_options': category_options,
            'subcategory_options': (
                selected_category_model.subcategories.filter(is_active=True)
                if selected_category_model
                else ()
            ),
            'selected_category': selected_category,
            'selected_subcategory': selected_subcategory,
        },
    )


def category_detail(request, category_slug):
    category = (
        RepairGuideCategory.objects.filter(
            slug=category_slug,
            is_active=True,
        )
        .prefetch_related('subcategories', 'related_categories')
        .first()
    )
    if category is None:
        category = CATEGORIES_BY_SLUG.get(category_slug)
    if category is None:
        raise Http404

    query = request.GET.get('q', '').strip()[:100]
    selected_item = request.GET.get('item', '').strip()[:100]
    repair_type = request.GET.get('type', '').strip()
    if isinstance(category, dict):
        category_data = _category_display_data(None, category)
        category_model = None
        products = _products_for_category(category_data)
        related_categories = tuple(
            CATEGORIES_BY_SLUG[slug]
            for slug in category_data['related']
            if slug in CATEGORIES_BY_SLUG
        )
        guide_queryset = RepairGuide.objects.none()
        subcategories = ()
    else:
        category_model = category
        legacy_data = CATEGORIES_BY_SLUG.get(category.slug)
        category_data = _category_display_data(category, legacy_data)
        products = _products_for_database_category(category)
        related_categories = [
            _category_display_data(item, CATEGORIES_BY_SLUG.get(item.slug))
            for item in category.related_categories.filter(is_active=True)
        ]
        subcategories = category.subcategories.filter(is_active=True)
        guide_queryset = RepairGuide.objects.filter(category=category_model)
    if selected_item:
        products = _product_search(products, selected_item)
    if query:
        products = _product_search(products, query)

    page_obj = Paginator(products, 8).get_page(request.GET.get('page'))
    guides = _filter_guides(
        guide_queryset.filter(status=RepairGuide.STATUS_PUBLISHED),
        request,
        query=query,
        selected_item=selected_item,
    )
    if repair_type == 'professional':
        guides = RepairGuide.objects.none()
    guide_page = Paginator(guides, 8).get_page(request.GET.get('guide_page'))
    return render(
        request,
        'repair_guides/category.html',
        {
            'category': category_data,
            'category_model': category_model,
            'related_categories': related_categories,
            'subcategories': subcategories,
            'query': query,
            'selected_item': selected_item,
            'products': page_obj.object_list,
            'page_obj': page_obj,
            'guides': guide_page.object_list,
            'guide_page': guide_page,
            'difficulty_choices': RepairGuide.DIFFICULTY_CHOICES,
            'selected_difficulty': request.GET.get('difficulty', ''),
            'selected_resource_type': request.GET.get('resource', ''),
            'max_minutes': request.GET.get('max_minutes', ''),
            'can_contribute': can_contribute_guides(request.user),
            'repair_type': repair_type,
        },
    )


def _products_for_database_category(category):
    matches = Q()
    terms = [category.name, *category.search_terms]
    for subcategory in category.subcategories.filter(is_active=True):
        terms.extend((subcategory.name, subcategory.description))
    for term in terms:
        if term:
            matches |= (
                Q(name__icontains=term)
                | Q(description__icontains=term)
                | Q(category__icontains=term)
            )
    if not matches:
        return marketable_products(Product.objects.none()).select_related('shop')
    return (
        marketable_products(
            Product.objects.filter(stock_quantity__gt=0).filter(matches)
        )
        .select_related('shop')
        .order_by('name', 'pk')
    )


def _category_display_data(category, fallback=None):
    fallback = fallback or {}
    if category is None:
        if not fallback:
            return {}
        return {
            **fallback,
            'image_src': (
                fallback.get('image_src')
                or static(
                    fallback.get(
                        'image',
                        'image/beni_separate_images/placeholders/no-image.png',
                    )
                )
            ),
        }
    subcategories = tuple(
        category.subcategories.filter(is_active=True).values_list(
            'name',
            flat=True,
        )
    )
    return {
        **fallback,
        'name': category.name,
        'slug': category.slug,
        'description': category.description,
        'item_types': subcategories,
        'safety': category.safety_notice or fallback.get('safety', ''),
        'image_src': (
            category.image.url
            if category.image
            else fallback.get('image_src')
            or static(
                fallback.get(
                    'image',
                    'image/beni_separate_images/placeholders/no-image.png',
                )
            )
        ),
        'image_alt': fallback.get('image_alt', category.name),
        'related': fallback.get('related', ()),
    }


def _category_matches(category, query):
    query = query.casefold()
    return (
        query in category['name'].casefold()
        or query in category['description'].casefold()
        or any(query in item.casefold() for item in category['item_types'])
    )


def _filter_guides(queryset, request, *, query='', selected_item=''):
    difficulty = request.GET.get('difficulty', '').strip()
    if difficulty in dict(RepairGuide.DIFFICULTY_CHOICES):
        queryset = queryset.filter(difficulty=difficulty)

    max_minutes = request.GET.get('max_minutes', '').strip()
    if max_minutes.isdigit() and 0 < int(max_minutes) <= 1440:
        queryset = queryset.filter(estimated_minutes__lte=int(max_minutes))

    resource_type = request.GET.get('resource', '').strip()
    if resource_type in dict(RepairGuideResource.TYPE_CHOICES):
        queryset = queryset.filter(resources__resource_type=resource_type)

    if selected_item:
        queryset = queryset.filter(
            Q(item_type__icontains=selected_item)
            | Q(subcategory__name__iexact=selected_item)
        )
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(category__name__icontains=query)
            | Q(subcategory__name__icontains=query)
            | Q(item_type__icontains=query)
            | Q(supported_model__icontains=query)
            | Q(symptoms__icontains=query)
            | Q(possible_causes__icontains=query)
            | Q(diagnosis__icontains=query)
            | Q(resources__name__icontains=query)
        )
    return (
        queryset.annotate(
            helpful_count=Count(
                'feedback',
                filter=Q(feedback__is_helpful=True),
                distinct=True,
            ),
        )
        .select_related('category', 'subcategory', 'author')
        .prefetch_related('steps', 'resources')
        .distinct()
        .order_by('-helpful_count', '-published_at', '-pk')
    )


def guide_detail(request, slug):
    guide = get_object_or_404(
        RepairGuide.objects.select_related(
            'category',
            'subcategory',
            'author',
        ).prefetch_related(
            'steps',
            'resources__product__shop',
            'related_guides',
        ),
        slug=slug,
    )
    if (
        guide.status != RepairGuide.STATUS_PUBLISHED
        and not (
            request.user.is_authenticated
            and (request.user.is_staff or guide.author_id == request.user.pk)
        )
    ):
        raise Http404

    resources = list(guide.resources.all())
    linked_shop_ids = {
        resource.product.shop_id
        for resource in resources
        if resource.product_id
    }
    eligible_shop_ids = set(
        eligible_shop_verifications(
            shop_ids=linked_shop_ids,
        ).values_list('shop_id', flat=True)
    )
    available_resources = []
    for resource in resources:
        product = resource.product
        product_available = bool(
            product
            and product.stock_quantity > 0
            and is_product_marketable(
                product,
                eligible_shop_ids=eligible_shop_ids,
            )
        )
        available_resources.append({
            'resource': resource,
            'product_available': product_available,
            'compatibility_confirmed': (
                resource.compatibility_verified and product_available
            ),
        })

    context = {
        'guide': guide,
        'resources': available_resources,
        'related_guides': guide.related_guides.filter(
            status=RepairGuide.STATUS_PUBLISHED,
        ),
        'helpful_count': guide.feedback.filter(is_helpful=True).count(),
        'not_helpful_count': guide.feedback.filter(is_helpful=False).count(),
        'can_edit': can_edit_guide(request.user, guide),
        'user_feedback': (
            guide.feedback.filter(user=request.user).first()
            if request.user.is_authenticated
            else None
        ),
    }
    return render(request, 'repair_guides/guide_detail.html', context)


@login_required
def guide_submit(request, slug=None):
    if not can_contribute_guides(request.user):
        raise PermissionDenied
    guide = None
    if slug is not None:
        guide = get_object_or_404(RepairGuide, slug=slug)
        if not can_edit_guide(request.user, guide):
            raise Http404

    form = RepairGuideForm(request.POST or None, instance=guide)
    step_formset = RepairGuideStepFormSet(
        request.POST or None,
        request.FILES or None,
        instance=guide or RepairGuide(),
        prefix='steps',
    )
    resource_formset = RepairGuideResourceFormSet(
        request.POST or None,
        instance=guide or RepairGuide(),
        prefix='resources',
    )
    form_is_valid = False
    steps_are_valid = False
    resources_are_valid = False
    if request.method == 'POST':
        if request.POST.get('action') == 'save_draft':
            step_formset.min_num = 0
            step_formset.validate_min = False
        form_is_valid = form.is_valid()
        steps_are_valid = step_formset.is_valid()
        resources_are_valid = resource_formset.is_valid()
    if form_is_valid and steps_are_valid and resources_are_valid:
        with transaction.atomic():
            guide = form.save(commit=False)
            if guide.pk is None:
                guide.author = request.user
            action = request.POST.get('action')
            guide.status = (
                RepairGuide.STATUS_DRAFT
                if action == 'save_draft'
                else RepairGuide.STATUS_SUBMITTED
            )
            guide.reviewer = None
            guide.moderation_note = ''
            guide.published_at = None
            guide.save()
            form.save_m2m()
            step_formset.instance = guide
            resource_formset.instance = guide
            step_formset.save()
            resource_formset.save()
        messages.success(
            request,
            'Guide saved as a draft.'
            if guide.status == RepairGuide.STATUS_DRAFT
            else 'Guide submitted for review.',
        )
        return redirect('repair_guides:guide', slug=guide.slug)

    return render(
        request,
        'repair_guides/guide_form.html',
        {
            'form': form,
            'step_formset': step_formset,
            'resource_formset': resource_formset,
            'guide': guide,
        },
    )


@login_required
@require_POST
def guide_feedback(request, slug):
    guide = get_object_or_404(
        RepairGuide,
        slug=slug,
        status=RepairGuide.STATUS_PUBLISHED,
    )
    value = request.POST.get('helpful')
    if value not in ('yes', 'no'):
        raise Http404
    guide.feedback.update_or_create(
        user=request.user,
        defaults={'is_helpful': value == 'yes'},
    )
    messages.success(request, 'Thanks for sharing your feedback.')
    return redirect('repair_guides:guide', slug=slug)


@login_required
@require_POST
def guide_report(request, slug):
    guide = get_object_or_404(
        RepairGuide,
        slug=slug,
        status=RepairGuide.STATUS_PUBLISHED,
    )
    form = ContentReportForm(request.POST)
    if form.is_valid():
        ContentReport.objects.create(
            reporter=request.user,
            guide=guide,
            reason=form.cleaned_data['reason'],
        )
        messages.success(request, 'Your report was sent to the moderators.')
        return redirect('repair_guides:guide', slug=slug)
    return render(
        request,
        'repair_guides/report_form.html',
        {
            'form': form,
            'content': guide,
            'cancel_url': reverse('repair_guides:guide', args=(guide.slug,)),
        },
    )


def question_list(request, category_slug=None):
    questions = RepairQuestion.objects.filter(
        status=RepairQuestion.STATUS_PUBLISHED,
    ).select_related('category', 'subcategory', 'author').annotate(
        helpful_count=Count('votes', filter=Q(votes__is_helpful=True)),
    )
    category = None
    if category_slug:
        category = get_object_or_404(
            RepairGuideCategory,
            slug=category_slug,
            is_active=True,
        )
        questions = questions.filter(category=category)
    query = request.GET.get('q', '').strip()[:100]
    if query:
        questions = questions.filter(
            Q(title__icontains=query)
            | Q(body__icontains=query)
            | Q(category__name__icontains=query)
            | Q(subcategory__name__icontains=query)
        )
    page_obj = Paginator(questions.order_by('-created_at', '-pk'), 20).get_page(
        request.GET.get('page')
    )
    return render(
        request,
        'repair_guides/question_list.html',
        {
            'questions': page_obj.object_list,
            'page_obj': page_obj,
            'category': category,
            'query': query,
        },
    )


def question_detail(request, question_id):
    question = get_object_or_404(
        RepairQuestion.objects.select_related(
            'category',
            'subcategory',
            'author',
            'related_guide',
            'related_product__shop',
        ).annotate(
            helpful_count=Count('votes', filter=Q(votes__is_helpful=True)),
        ),
        pk=question_id,
    )
    is_owner = (
        request.user.is_authenticated
        and question.author_id == request.user.pk
    )
    if (
        question.status != RepairQuestion.STATUS_PUBLISHED
        and not (is_owner or request.user.is_staff)
    ):
        raise Http404

    answer_query = question.answers.select_related('author').annotate(
        helpful_count=Count('votes', filter=Q(votes__is_helpful=True)),
    )
    answers = answer_query.filter(status=RepairAnswer.STATUS_PUBLISHED)
    if request.user.is_authenticated:
        answers = answers | answer_query.filter(author=request.user)
    related_guide = question.related_guide
    if (
        related_guide
        and related_guide.status != RepairGuide.STATUS_PUBLISHED
    ):
        related_guide = None
    related_product_available = bool(
        question.related_product
        and question.related_product.stock_quantity > 0
        and is_product_marketable(question.related_product)
    )
    answer_form = RepairAnswerForm()
    if request.method == 'POST' and not request.user.is_authenticated:
        raise PermissionDenied
    if (
        request.method == 'POST'
        and can_contribute_guides(request.user)
        and question.status == RepairQuestion.STATUS_PUBLISHED
    ):
        answer_form = RepairAnswerForm(request.POST)
        if answer_form.is_valid():
            answer = answer_form.save(commit=False)
            answer.question = question
            answer.author = request.user
            answer.save()
            messages.success(
                request,
                'Your answer was submitted for moderator review.',
            )
            return redirect('repair_guides:question', question_id=question.pk)
    elif request.method == 'POST' and request.user.is_authenticated:
        raise PermissionDenied
    return render(
        request,
        'repair_guides/question_detail.html',
        {
            'question': question,
            'answers': answers.order_by('created_at', 'pk'),
            'answer_form': answer_form,
            'is_owner': is_owner,
            'can_answer': can_contribute_guides(request.user),
            'related_guide': related_guide,
            'related_product_available': related_product_available,
        },
    )


@login_required
def question_submit(request, question_id=None):
    question = None
    if question_id is not None:
        question = get_object_or_404(RepairQuestion, pk=question_id)
        if question.author_id != request.user.pk and not request.user.is_staff:
            raise Http404
        if question.status not in (
            RepairQuestion.STATUS_PENDING,
            RepairQuestion.STATUS_REJECTED,
        ) and not request.user.is_staff:
            raise PermissionDenied
    form = RepairQuestionForm(request.POST or None, request.FILES or None, instance=question)
    if request.method == 'POST' and form.is_valid():
        question = form.save(commit=False)
        if question.pk is None:
            question.author = request.user
        question.status = RepairQuestion.STATUS_PENDING
        question.reviewer = None
        question.save()
        messages.success(request, 'Your question was submitted for moderation.')
        return redirect('repair_guides:question', question_id=question.pk)
    return render(
        request,
        'repair_guides/question_form.html',
        {'form': form, 'question': question},
    )


@login_required
@require_POST
def question_delete(request, question_id):
    question = get_object_or_404(RepairQuestion, pk=question_id)
    if question.author_id != request.user.pk:
        raise Http404
    if question.status not in (
        RepairQuestion.STATUS_PENDING,
        RepairQuestion.STATUS_REJECTED,
    ):
        raise PermissionDenied
    question.delete()
    messages.success(request, 'Your question was deleted.')
    return redirect('repair_guides:questions')


@login_required
@require_POST
def question_vote(request, question_id):
    question = get_object_or_404(
        RepairQuestion,
        pk=question_id,
        status=RepairQuestion.STATUS_PUBLISHED,
    )
    value = request.POST.get('helpful')
    if value not in ('yes', 'no'):
        raise Http404
    is_helpful = value == 'yes'
    QuestionVote.objects.update_or_create(
        question=question,
        user=request.user,
        defaults={'is_helpful': is_helpful},
    )
    return redirect('repair_guides:question', question_id=question.pk)


@login_required
def answer_submit(request, answer_id=None, question_id=None):
    answer = None
    question = None
    if answer_id is not None:
        answer = get_object_or_404(
            RepairAnswer.objects.select_related('question'),
            pk=answer_id,
        )
        if answer.author_id != request.user.pk and not request.user.is_staff:
            raise Http404
        if (
            not request.user.is_staff
            and answer.status not in (
                RepairAnswer.STATUS_PENDING,
                RepairAnswer.STATUS_REJECTED,
            )
        ):
            raise PermissionDenied
        question = answer.question
    elif question_id is not None:
        question = get_object_or_404(
            RepairQuestion,
            pk=question_id,
            status=RepairQuestion.STATUS_PUBLISHED,
        )
    if not can_contribute_guides(request.user):
        raise PermissionDenied
    form = RepairAnswerForm(request.POST or None, instance=answer)
    if request.method == 'POST' and form.is_valid():
        answer = form.save(commit=False)
        if answer.pk is None:
            answer.question = question
            answer.author = request.user
        answer.status = RepairAnswer.STATUS_PENDING
        answer.reviewer = None
        answer.save()
        messages.success(request, 'Your answer was submitted for review.')
        return redirect(
            'repair_guides:question',
            question_id=answer.question_id,
        )
    return render(
        request,
        'repair_guides/answer_form.html',
        {'form': form, 'answer': answer},
    )


@login_required
@require_POST
def answer_delete(request, answer_id):
    answer = get_object_or_404(RepairAnswer, pk=answer_id)
    if answer.author_id != request.user.pk:
        raise Http404
    if answer.status not in (
        RepairAnswer.STATUS_PENDING,
        RepairAnswer.STATUS_REJECTED,
    ):
        raise PermissionDenied
    question_id = answer.question_id
    answer.delete()
    messages.success(request, 'Your answer was deleted.')
    return redirect('repair_guides:question', question_id=question_id)


@login_required
@require_POST
def answer_vote(request, answer_id):
    answer = get_object_or_404(
        RepairAnswer.objects.select_related('question'),
        pk=answer_id,
        status=RepairAnswer.STATUS_PUBLISHED,
        question__status=RepairQuestion.STATUS_PUBLISHED,
    )
    value = request.POST.get('helpful')
    if value not in ('yes', 'no'):
        raise Http404
    is_helpful = value == 'yes'
    AnswerVote.objects.update_or_create(
        answer=answer,
        user=request.user,
        defaults={'is_helpful': is_helpful},
    )
    return redirect('repair_guides:question', question_id=answer.question_id)


@login_required
@require_POST
def question_report(request, question_id):
    question = get_object_or_404(
        RepairQuestion,
        pk=question_id,
        status=RepairQuestion.STATUS_PUBLISHED,
    )
    form = ContentReportForm(request.POST)
    if form.is_valid():
        ContentReport.objects.create(
            reporter=request.user,
            question=question,
            reason=form.cleaned_data['reason'],
        )
        messages.success(request, 'Your report was sent to the moderators.')
        return redirect('repair_guides:question', question_id=question.pk)
    return render(
        request,
        'repair_guides/report_form.html',
        {
            'form': form,
            'content': question,
            'cancel_url': reverse(
                'repair_guides:question',
                args=(question.pk,),
            ),
        },
    )


@login_required
@require_POST
def answer_report(request, answer_id):
    answer = get_object_or_404(
        RepairAnswer.objects.select_related('question'),
        pk=answer_id,
        status=RepairAnswer.STATUS_PUBLISHED,
        question__status=RepairQuestion.STATUS_PUBLISHED,
    )
    form = ContentReportForm(request.POST)
    if form.is_valid():
        ContentReport.objects.create(
            reporter=request.user,
            answer=answer,
            reason=form.cleaned_data['reason'],
        )
        messages.success(request, 'Your report was sent to the moderators.')
        return redirect(
            'repair_guides:question',
            question_id=answer.question_id,
        )
    return render(
        request,
        'repair_guides/report_form.html',
        {
            'form': form,
            'content': answer,
            'cancel_url': reverse(
                'repair_guides:question',
                args=(answer.question_id,),
            ),
        },
    )


@login_required
def moderation_queue(request):
    if not request.user.is_staff:
        raise PermissionDenied
    return render(
        request,
        'repair_guides/moderation_queue.html',
        {
            'guides': RepairGuide.objects.filter(
                status=RepairGuide.STATUS_SUBMITTED,
            ).select_related('author', 'category'),
            'questions': RepairQuestion.objects.filter(
                status=RepairQuestion.STATUS_PENDING,
            ).select_related('author', 'category'),
            'answers': RepairAnswer.objects.filter(
                status=RepairAnswer.STATUS_PENDING,
            ).select_related('author', 'question'),
            'reports': ContentReport.objects.filter(
                status=ContentReport.STATUS_PENDING,
            ).select_related('reporter', 'guide', 'question', 'answer'),
        },
    )


@login_required
@require_POST
def moderate_content(request, content_type, object_id):
    if not request.user.is_staff:
        raise PermissionDenied
    decision = request.POST.get('decision')
    note = request.POST.get('note', '').strip()[:2000]
    try:
        if content_type == 'guide':
            item = moderate_guide(
                guide_id=object_id,
                moderator=request.user,
                status=decision,
                note=note,
            )
        elif content_type == 'question':
            item = moderate_question(
                question_id=object_id,
                moderator=request.user,
                status=decision,
                note=note,
            )
        elif content_type == 'answer':
            item = moderate_answer(
                answer_id=object_id,
                moderator=request.user,
                status=decision,
                note=note,
            )
        else:
            raise Http404
    except ContentWorkflowError as error:
        messages.error(request, str(error))
        return redirect('repair_guides:moderation')
    if item is None:
        raise Http404
    messages.success(request, 'The content moderation decision was recorded.')
    return redirect('repair_guides:moderation')


@login_required
@require_POST
def moderate_report(request, report_id):
    if not request.user.is_staff:
        raise PermissionDenied
    decision = request.POST.get('decision')
    if decision not in (
        ContentReport.STATUS_RESOLVED,
        ContentReport.STATUS_DISMISSED,
    ):
        raise Http404
    with transaction.atomic():
        report = get_object_or_404(
            ContentReport.objects.select_for_update(),
            pk=report_id,
            status=ContentReport.STATUS_PENDING,
        )
        report.status = decision
        report.moderator = request.user
        report.moderator_note = request.POST.get('note', '').strip()[:2000]
        report.resolved_at = timezone.now()
        report.save(
            update_fields=(
                'status',
                'moderator',
                'moderator_note',
                'resolved_at',
            )
        )
    messages.success(request, 'The report decision was recorded.')
    return redirect('repair_guides:moderation')
