from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from beni.upload_paths import (
    repair_guide_category_image_path,
    repair_guide_step_image_path,
    repair_question_image_path,
)
from products.image_validation import validate_product_image


class RepairGuideCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField()
    image = models.ImageField(
        upload_to=repair_guide_category_image_path,
        blank=True,
        validators=[validate_product_image],
    )
    search_terms = models.JSONField(default=list, blank=True)
    booking_category = models.CharField(max_length=100, blank=True)
    safety_notice = models.TextField(blank=True)
    related_categories = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='related_to',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order', 'name', 'pk')
        indexes = [
            models.Index(fields=('is_active', 'sort_order')),
        ]

    def __str__(self):
        return self.name


class RepairGuideSubcategory(models.Model):
    category = models.ForeignKey(
        RepairGuideCategory,
        on_delete=models.PROTECT,
        related_name='subcategories',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('sort_order', 'name', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('category', 'slug'),
                name='repair_guides_subcategory_slug_unique',
            ),
        ]

    def __str__(self):
        return f'{self.category.name} / {self.name}'


class RepairGuide(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted for review'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_REJECTED, 'Changes requested'),
    ]

    DIFFICULTY_BEGINNER = 'beginner'
    DIFFICULTY_INTERMEDIATE = 'intermediate'
    DIFFICULTY_ADVANCED = 'advanced'
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_BEGINNER, 'Beginner'),
        (DIFFICULTY_INTERMEDIATE, 'Intermediate'),
        (DIFFICULTY_ADVANCED, 'Advanced'),
    ]

    category = models.ForeignKey(
        RepairGuideCategory,
        on_delete=models.PROTECT,
        related_name='guides',
    )
    subcategory = models.ForeignKey(
        RepairGuideSubcategory,
        on_delete=models.PROTECT,
        related_name='guides',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.CharField(max_length=400)
    item_type = models.CharField(max_length=120)
    supported_model = models.CharField(max_length=180, blank=True)
    symptoms = models.TextField(blank=True)
    possible_causes = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=16,
        choices=DIFFICULTY_CHOICES,
        default=DIFFICULTY_BEGINNER,
    )
    estimated_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    safety_warnings = models.TextField(blank=True)
    preparation = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    troubleshooting = models.TextField(blank=True)
    related_guides = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='related_to',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_guides_authored',
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='repair_guides_reviewed',
        null=True,
        blank=True,
    )
    moderation_note = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(2000)],
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-published_at', '-pk')
        indexes = [
            models.Index(fields=('category', 'status', 'published_at')),
            models.Index(fields=('difficulty', 'estimated_minutes')),
        ]

    def clean(self):
        super().clean()
        if (
            self.subcategory_id
            and self.category_id
            and self.subcategory.category_id != self.category_id
        ):
            raise ValidationError({
                'subcategory': 'Choose an item type within this category.',
            })

    def __str__(self):
        return self.title


class RepairGuideStep(models.Model):
    guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    position = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=180, blank=True)
    instructions = models.TextField()
    image = models.ImageField(
        upload_to=repair_guide_step_image_path,
        blank=True,
        validators=[validate_product_image],
    )

    class Meta:
        ordering = ('position', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('guide', 'position'),
                name='repair_guide_step_position_unique',
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name='repair_guide_step_position_positive',
            ),
        ]

    def __str__(self):
        return f'{self.guide.title} — step {self.position}'


class RepairGuideResource(models.Model):
    TYPE_TOOL = 'tool'
    TYPE_PART = 'part'
    TYPE_MATERIAL = 'material'
    TYPE_CHOICES = [
        (TYPE_TOOL, 'Tool'),
        (TYPE_PART, 'Spare part'),
        (TYPE_MATERIAL, 'Material'),
    ]

    guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.CASCADE,
        related_name='resources',
    )
    resource_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    name = models.CharField(max_length=180)
    quantity = models.CharField(max_length=60, blank=True)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='repair_guide_resources',
        null=True,
        blank=True,
    )
    compatibility_verified = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('position', 'pk')
        indexes = [
            models.Index(fields=('guide', 'resource_type')),
        ]

    def __str__(self):
        return f'{self.get_resource_type_display()}: {self.name}'


class RepairGuideFeedback(models.Model):
    guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.CASCADE,
        related_name='feedback',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='repair_guide_feedback',
    )
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('guide', 'user'),
                name='repair_guide_feedback_user_unique',
            ),
        ]


class RepairQuestion(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending moderation'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_REJECTED, 'Not published'),
    ]

    category = models.ForeignKey(
        RepairGuideCategory,
        on_delete=models.PROTECT,
        related_name='questions',
    )
    subcategory = models.ForeignKey(
        RepairGuideSubcategory,
        on_delete=models.PROTECT,
        related_name='questions',
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_questions',
    )
    title = models.CharField(max_length=180)
    body = models.TextField(validators=[MaxLengthValidator(5000)])
    image = models.ImageField(
        upload_to=repair_question_image_path,
        blank=True,
        validators=[validate_product_image],
    )
    related_guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.SET_NULL,
        related_name='questions',
        null=True,
        blank=True,
    )
    related_product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        related_name='repair_questions',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='repair_questions_reviewed',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [
            models.Index(fields=('category', 'status', 'created_at')),
        ]

    def clean(self):
        super().clean()
        if (
            self.subcategory_id
            and self.category_id
            and self.subcategory.category_id != self.category_id
        ):
            raise ValidationError({
                'subcategory': 'Choose an item type within this category.',
            })

    def __str__(self):
        return self.title


class RepairAnswer(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending moderation'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_REJECTED, 'Not published'),
    ]

    question = models.ForeignKey(
        RepairQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_answers',
    )
    body = models.TextField(validators=[MaxLengthValidator(5000)])
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='repair_answers_reviewed',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created_at', 'pk')
        indexes = [
            models.Index(fields=('question', 'status', 'created_at')),
        ]


class QuestionVote(models.Model):
    question = models.ForeignKey(
        RepairQuestion,
        on_delete=models.CASCADE,
        related_name='votes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='repair_question_votes',
    )
    is_helpful = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('question', 'user'),
                name='repair_question_vote_user_unique',
            ),
        ]


class AnswerVote(models.Model):
    answer = models.ForeignKey(
        RepairAnswer,
        on_delete=models.CASCADE,
        related_name='votes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='repair_answer_votes',
    )
    is_helpful = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('answer', 'user'),
                name='repair_answer_vote_user_unique',
            ),
        ]


class ContentReport(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending review'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_content_reports',
    )
    guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.CASCADE,
        related_name='reports',
        null=True,
        blank=True,
    )
    question = models.ForeignKey(
        RepairQuestion,
        on_delete=models.CASCADE,
        related_name='reports',
        null=True,
        blank=True,
    )
    answer = models.ForeignKey(
        RepairAnswer,
        on_delete=models.CASCADE,
        related_name='reports',
        null=True,
        blank=True,
    )
    reason = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='repair_reports_moderated',
        null=True,
        blank=True,
    )
    moderator_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('status', '-created_at', '-pk')
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(guide__isnull=False, question__isnull=True, answer__isnull=True)
                    | Q(guide__isnull=True, question__isnull=False, answer__isnull=True)
                    | Q(guide__isnull=True, question__isnull=True, answer__isnull=False)
                ),
                name='repair_content_report_one_target',
            ),
        ]
        indexes = [
            models.Index(fields=('status', 'created_at')),
        ]

    def clean(self):
        super().clean()
        if sum(bool(value) for value in (
            self.guide_id,
            self.question_id,
            self.answer_id,
        )) != 1:
            raise ValidationError(
                'A report must reference exactly one guide, question, or answer.'
            )


class ContentModerationEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_moderation_events',
    )
    guide = models.ForeignKey(
        RepairGuide,
        on_delete=models.CASCADE,
        related_name='moderation_events',
        null=True,
        blank=True,
    )
    question = models.ForeignKey(
        RepairQuestion,
        on_delete=models.CASCADE,
        related_name='moderation_events',
        null=True,
        blank=True,
    )
    answer = models.ForeignKey(
        RepairAnswer,
        on_delete=models.CASCADE,
        related_name='moderation_events',
        null=True,
        blank=True,
    )
    previous_status = models.CharField(max_length=12, blank=True)
    new_status = models.CharField(max_length=12)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(guide__isnull=False, question__isnull=True, answer__isnull=True)
                    | Q(guide__isnull=True, question__isnull=False, answer__isnull=True)
                    | Q(guide__isnull=True, question__isnull=True, answer__isnull=False)
                ),
                name='repair_moderation_event_one_target',
            ),
        ]
        indexes = [
            models.Index(fields=('created_at', 'actor')),
        ]

    def clean(self):
        super().clean()
        if sum(bool(value) for value in (
            self.guide_id,
            self.question_id,
            self.answer_id,
        )) != 1:
            raise ValidationError(
                'A moderation event must reference exactly one content item.'
            )
