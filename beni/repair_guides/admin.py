from django.contrib import admin
from django.db import transaction

from .models import (
    ContentModerationEvent,
    ContentReport,
    RepairAnswer,
    RepairGuide,
    RepairGuideCategory,
    RepairGuideResource,
    RepairGuideStep,
    RepairGuideSubcategory,
    RepairQuestion,
)


@admin.register(RepairGuideCategory)
class RepairGuideCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('related_categories',)


@admin.register(RepairGuideSubcategory)
class RepairGuideSubcategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'sort_order')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description', 'category__name')
    prepopulated_fields = {'slug': ('name',)}


class ReadOnlyContentAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(
            field.name
            for field in (*self.model._meta.fields, *self.model._meta.many_to_many)
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RepairGuide)
class RepairGuideAdmin(ReadOnlyContentAdmin):
    list_display = ('title', 'category', 'author', 'status', 'updated_at')
    list_filter = ('status', 'category', 'difficulty')
    search_fields = ('title', 'summary', 'item_type', 'author__username')


class RepairGuideStepAdmin(admin.ModelAdmin):
    list_display = ('guide', 'position', 'title')
    list_filter = ('guide__category',)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ('guide',) if obj else ()

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        previous_status = obj.guide.status
        super().save_model(request, obj, form, change)
        guide = obj.guide
        if guide.status == RepairGuide.STATUS_PUBLISHED:
            guide.status = RepairGuide.STATUS_SUBMITTED
            guide.reviewer = None
            guide.moderation_note = ''
            guide.published_at = None
            guide.save(
                update_fields=(
                    'status',
                    'reviewer',
                    'moderation_note',
                    'published_at',
                    'updated_at',
                )
            )
        ContentModerationEvent.objects.create(
            actor=request.user,
            guide=guide,
            previous_status=previous_status,
            new_status=guide.status,
            note=f'Repair step {obj.pk} saved in the admin.',
        )


class RepairGuideResourceAdmin(admin.ModelAdmin):
    list_display = ('guide', 'resource_type', 'name', 'product', 'compatibility_verified')
    list_filter = ('resource_type', 'compatibility_verified')
    search_fields = ('name', 'guide__title')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ('guide',) if obj else ()

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        previous_status = obj.guide.status
        super().save_model(request, obj, form, change)
        guide = obj.guide
        if guide.status == RepairGuide.STATUS_PUBLISHED:
            guide.status = RepairGuide.STATUS_SUBMITTED
            guide.reviewer = None
            guide.moderation_note = ''
            guide.published_at = None
            guide.save(
                update_fields=(
                    'status',
                    'reviewer',
                    'moderation_note',
                    'published_at',
                    'updated_at',
                )
            )
        ContentModerationEvent.objects.create(
            actor=request.user,
            guide=guide,
            previous_status=previous_status,
            new_status=guide.status,
            note=f'Repair resource {obj.pk} saved in the admin.',
        )


@admin.register(RepairQuestion)
class RepairQuestionAdmin(ReadOnlyContentAdmin):
    readonly_fields = tuple(field.name for field in RepairQuestion._meta.fields)
    list_display = ('title', 'category', 'author', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'body', 'author__username')


@admin.register(RepairAnswer)
class RepairAnswerAdmin(ReadOnlyContentAdmin):
    readonly_fields = tuple(field.name for field in RepairAnswer._meta.fields)
    list_display = ('question', 'author', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('body', 'author__username', 'question__title')


@admin.register(ContentReport)
class ContentReportAdmin(ReadOnlyContentAdmin):
    readonly_fields = tuple(field.name for field in ContentReport._meta.fields)
    list_display = ('id', 'reporter', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(ContentModerationEvent)
class ContentModerationEventAdmin(ReadOnlyContentAdmin):
    readonly_fields = tuple(
        field.name for field in ContentModerationEvent._meta.fields
    )
    list_display = ('actor', 'new_status', 'created_at')


admin.site.register(RepairGuideStep, RepairGuideStepAdmin)
admin.site.register(RepairGuideResource, RepairGuideResourceAdmin)
