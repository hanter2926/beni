from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import (
    ContentModerationEvent,
    RepairAnswer,
    RepairGuide,
    RepairQuestion,
)


class ContentWorkflowError(Exception):
    pass


@transaction.atomic
def moderate_guide(*, guide_id, moderator, status, note=''):
    if not moderator.is_active or not moderator.is_staff:
        raise PermissionDenied
    guide = RepairGuide.objects.select_for_update().filter(
        pk=guide_id,
    ).first()
    if guide is None:
        return None
    if guide.status != RepairGuide.STATUS_SUBMITTED:
        raise ContentWorkflowError('This guide is not awaiting moderation.')
    if status not in (
        RepairGuide.STATUS_PUBLISHED,
        RepairGuide.STATUS_REJECTED,
    ):
        raise ContentWorkflowError('Choose a valid guide moderation decision.')
    if status == RepairGuide.STATUS_REJECTED and not note.strip():
        raise ContentWorkflowError('Add a note when requesting guide changes.')
    if (
        status == RepairGuide.STATUS_PUBLISHED
        and not guide.steps.exists()
    ):
        raise ContentWorkflowError(
            'Add at least one repair step before publishing this guide.'
        )

    previous_status = guide.status
    guide.status = status
    guide.reviewer = moderator
    guide.moderation_note = note.strip()
    guide.published_at = (
        timezone.now()
        if status == RepairGuide.STATUS_PUBLISHED
        else None
    )
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
        actor=moderator,
        guide=guide,
        previous_status=previous_status,
        new_status=status,
        note=note.strip(),
    )
    return guide


@transaction.atomic
def moderate_question(*, question_id, moderator, status, note=''):
    if not moderator.is_active or not moderator.is_staff:
        raise PermissionDenied
    question = RepairQuestion.objects.select_for_update().filter(
        pk=question_id,
    ).first()
    if question is None:
        return None
    if question.status != RepairQuestion.STATUS_PENDING:
        raise ContentWorkflowError('This question is not awaiting moderation.')
    if status not in (
        RepairQuestion.STATUS_PUBLISHED,
        RepairQuestion.STATUS_REJECTED,
    ):
        raise ContentWorkflowError('Choose a valid question moderation decision.')
    if status == RepairQuestion.STATUS_REJECTED and not note.strip():
        raise ContentWorkflowError('Add a note when rejecting this question.')
    previous_status = question.status
    question.status = status
    question.reviewer = moderator
    question.save(update_fields=('status', 'reviewer', 'updated_at'))
    ContentModerationEvent.objects.create(
        actor=moderator,
        question=question,
        previous_status=previous_status,
        new_status=status,
        note=note.strip(),
    )
    return question


@transaction.atomic
def moderate_answer(*, answer_id, moderator, status, note=''):
    if not moderator.is_active or not moderator.is_staff:
        raise PermissionDenied
    answer = RepairAnswer.objects.select_for_update().filter(
        pk=answer_id,
    ).first()
    if answer is None:
        return None
    if answer.status != RepairAnswer.STATUS_PENDING:
        raise ContentWorkflowError('This answer is not awaiting moderation.')
    if status not in (
        RepairAnswer.STATUS_PUBLISHED,
        RepairAnswer.STATUS_REJECTED,
    ):
        raise ContentWorkflowError('Choose a valid answer moderation decision.')
    if status == RepairAnswer.STATUS_REJECTED and not note.strip():
        raise ContentWorkflowError('Add a note when rejecting this answer.')
    if (
        status == RepairAnswer.STATUS_PUBLISHED
        and answer.question.status != RepairQuestion.STATUS_PUBLISHED
    ):
        raise ContentWorkflowError(
            'Publish the related question before publishing its answer.'
        )
    previous_status = answer.status
    answer.status = status
    answer.reviewer = moderator
    answer.save(update_fields=('status', 'reviewer', 'updated_at'))
    ContentModerationEvent.objects.create(
        actor=moderator,
        answer=answer,
        previous_status=previous_status,
        new_status=status,
        note=note.strip(),
    )
    return answer
