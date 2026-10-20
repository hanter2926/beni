from django.urls import path

from . import views

app_name = 'repair_guides'

urlpatterns = [
    path('', views.repair_guide_home, name='home'),
    path('guides/new/', views.guide_submit, name='guide_new'),
    path('guides/<slug:slug>/edit/', views.guide_submit, name='guide_edit'),
    path('guides/<slug:slug>/', views.guide_detail, name='guide'),
    path('guides/<slug:slug>/feedback/', views.guide_feedback, name='guide_feedback'),
    path('guides/<slug:slug>/report/', views.guide_report, name='guide_report'),
    path('questions/', views.question_list, name='questions'),
    path('questions/new/', views.question_submit, name='question_new'),
    path(
        'questions/category/<slug:category_slug>/',
        views.question_list,
        name='questions_category',
    ),
    path(
        'questions/<int:question_id>/edit/',
        views.question_submit,
        name='question_edit',
    ),
    path(
        'questions/<int:question_id>/delete/',
        views.question_delete,
        name='question_delete',
    ),
    path(
        'questions/<int:question_id>/vote/',
        views.question_vote,
        name='question_vote',
    ),
    path(
        'questions/<int:question_id>/report/',
        views.question_report,
        name='question_report',
    ),
    path(
        'questions/<int:question_id>/answers/new/',
        views.answer_submit,
        name='answer_new',
    ),
    path('questions/<int:question_id>/', views.question_detail, name='question'),
    path(
        'answers/<int:answer_id>/edit/',
        views.answer_submit,
        name='answer_edit',
    ),
    path(
        'answers/<int:answer_id>/delete/',
        views.answer_delete,
        name='answer_delete',
    ),
    path('answers/<int:answer_id>/vote/', views.answer_vote, name='answer_vote'),
    path('answers/<int:answer_id>/report/', views.answer_report, name='answer_report'),
    path('moderation/', views.moderation_queue, name='moderation'),
    path(
        'moderation/reports/<int:report_id>/',
        views.moderate_report,
        name='moderate_report',
    ),
    path(
        'moderation/<str:content_type>/<int:object_id>/',
        views.moderate_content,
        name='moderate_content',
    ),
    path('<slug:category_slug>/', views.category_detail, name='category'),
]
