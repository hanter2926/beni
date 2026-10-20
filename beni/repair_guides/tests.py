from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from products.models import Product
from shops.models import Shop
from verification.models import VerificationApplication

from .categories import CATEGORIES
from .forms import RepairQuestionForm
from .models import (
    ContentModerationEvent,
    ContentReport,
    RepairAnswer,
    RepairGuide,
    RepairGuideCategory,
    RepairGuideResource,
    RepairGuideStep,
    RepairQuestion,
)
from .permissions import CONTRIBUTOR_GROUP_NAME


class RepairGuideRouteTests(SimpleTestCase):
    def test_every_category_has_a_resolvable_public_page(self):
        for category in CATEGORIES:
            with self.subTest(category=category['slug']):
                url = reverse(
                    'repair_guides:category',
                    args=(category['slug'],),
                )
                self.assertEqual(url, f"/repair-guides/{category['slug']}/")
                image_path = Path(settings.BASE_DIR) / 'static' / category['image']
                self.assertTrue(image_path.is_file(), category['image'])

    def test_category_directory_route_is_named_and_public(self):
        self.assertEqual(
            reverse('repair_guides:home'),
            '/repair-guides/',
        )


class RepairGuideCatalogTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='repair-guide-shop-owner',
        )
        Profile.objects.create(
            user=self.owner,
            phone='+15550100091',
            phone_verified=True,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name='Verified Parts Shop',
            category='Electronics',
            phone='555-0191',
            address='1 Market Street',
            city='Test City',
            state='Test State',
            postal_code='12345',
        )
        VerificationApplication.objects.create(
            applicant=self.owner,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            aadhaar_status=VerificationApplication.CHECK_VERIFIED,
        )
        self.phone_product = Product.objects.create(
            shop=self.shop,
            name='Phone Screen Protector',
            description='Protective accessory for phones.',
            category='Phone accessories',
            price=Decimal('12.50'),
            stock_quantity=3,
        )
        self.out_of_stock_product = Product.objects.create(
            shop=self.shop,
            name='Phone Replacement Battery',
            category='Phone parts',
            price=Decimal('35.00'),
            stock_quantity=0,
        )
        self.inactive_product = Product.objects.create(
            shop=self.shop,
            name='Phone Cable Listing',
            category='Phone accessories',
            price=Decimal('8.00'),
            stock_quantity=5,
            is_active=False,
        )
        self.nonmatching_product = Product.objects.create(
            shop=self.shop,
            name='Wool Jacket',
            category='Apparel',
            price=Decimal('25.00'),
            stock_quantity=4,
        )

    def test_phone_category_uses_marketable_in_stock_products(self):
        response = self.client.get(
            reverse('repair_guides:category', args=('phone',))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone Screen Protector')
        self.assertContains(response, 'Verified Parts Shop')
        self.assertContains(response, '12.50')
        self.assertNotContains(response, self.out_of_stock_product.name)
        self.assertNotContains(response, self.inactive_product.name)
        self.assertNotContains(response, self.nonmatching_product.name)
        self.assertContains(response, 'No published guides match these filters yet')
        self.assertContains(response, 'confirm suitability before ordering')

    def test_category_search_filters_actual_products(self):
        response = self.client.get(
            reverse('repair_guides:category', args=('phone',)),
            {'q': 'screen'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone Screen Protector')
        self.assertNotContains(response, 'Phone Replacement Battery')
        self.assertNotContains(response, 'Wool Jacket')

    def test_home_search_filters_category_names_and_live_shop_products(self):
        response = self.client.get(
            reverse('repair_guides:home'),
            {'q': 'phone'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone')
        self.assertContains(response, 'Phone Screen Protector')
        self.assertNotContains(response, 'Wool Jacket')

    def test_unknown_category_returns_not_found(self):
        response = self.client.get(
            reverse('repair_guides:category', args=('unknown-category',))
        )

        self.assertEqual(response.status_code, 404)

    def test_every_category_page_renders(self):
        for category in CATEGORIES:
            with self.subTest(category=category['slug']):
                response = self.client.get(
                    reverse(
                        'repair_guides:category',
                        args=(category['slug'],),
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, category['name'])

    def test_booking_link_preserves_category_and_prefills_existing_booking_form(self):
        category_response = self.client.get(
            reverse('repair_guides:category', args=('phone',))
        )
        self.assertContains(
            category_response,
            reverse('bookings:customer_create') + '?category=phone',
        )

        customer = get_user_model().objects.create_user(
            username='repair-guide-customer',
        )
        Profile.objects.create(
            user=customer,
            phone='+15550100092',
            phone_verified=True,
        )
        self.client.force_login(customer)
        booking_response = self.client.get(
            reverse('bookings:customer_create'),
            {'category': 'phone'},
        )

        self.assertEqual(booking_response.status_code, 200)
        self.assertEqual(
            booking_response.context['form']['service_category'].value(),
            'Mobile repair',
        )
        self.assertEqual(
            booking_response.context['form']['problem_description'].value(),
            'Category: Phone\n\n',
        )


class RepairGuideWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='guide-author',
            password='test-password',
        )
        self.other_user = user_model.objects.create_user(
            username='other-member',
            password='test-password',
        )
        self.staff = user_model.objects.create_user(
            username='guide-moderator',
            password='test-password',
            is_staff=True,
        )
        contributor_group, _ = Group.objects.get_or_create(
            name=CONTRIBUTOR_GROUP_NAME,
        )
        self.contributor = user_model.objects.create_user(
            username='guide-contributor',
            password='test-password',
        )
        self.contributor.groups.add(contributor_group)
        self.category, _ = RepairGuideCategory.objects.get_or_create(
            slug='phone',
            defaults={
                'name': 'Phone',
                'description': 'Phone troubleshooting and repair guides.',
                'search_terms': ['mobile'],
                'booking_category': 'Mobile repair',
                'sort_order': 1,
            },
        )

    def create_guide(self, *, slug, status=RepairGuide.STATUS_PUBLISHED):
        published_at = timezone.now() if status == RepairGuide.STATUS_PUBLISHED else None
        guide = RepairGuide.objects.create(
            category=self.category,
            title=slug.replace('-', ' ').title(),
            slug=slug,
            summary='A reviewed repair guide summary.',
            item_type='Phone',
            symptoms='The phone does not charge.',
            difficulty=RepairGuide.DIFFICULTY_BEGINNER,
            estimated_minutes=20,
            author=self.owner,
            status=status,
            published_at=published_at,
        )
        RepairGuideStep.objects.create(
            guide=guide,
            position=1,
            title='Inspect safely',
            instructions='Disconnect power and inspect the exterior.',
        )
        return guide

    def create_question(self, *, status=RepairQuestion.STATUS_PUBLISHED):
        return RepairQuestion.objects.create(
            category=self.category,
            author=self.owner,
            title='Why will this phone not charge?',
            body='The device no longer charges through its port.',
            status=status,
        )

    def test_unpublished_guides_are_visible_only_to_their_author_or_staff(self):
        guide = self.create_guide(
            slug='private-draft',
            status=RepairGuide.STATUS_DRAFT,
        )
        url = reverse('repair_guides:guide', args=(guide.slug,))

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_only_published_guides_appear_in_public_browse_results(self):
        published = self.create_guide(slug='published-charging-guide')
        self.create_guide(
            slug='unpublished-charging-draft',
            status=RepairGuide.STATUS_SUBMITTED,
        )

        response = self.client.get(
            reverse('repair_guides:category', args=(self.category.slug,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.title)
        self.assertNotContains(response, 'Unpublished Charging Draft')

    def test_category_filters_narrow_published_guides_by_difficulty_time_and_resource(self):
        matching = self.create_guide(slug='battery-port-cleaning')
        RepairGuideResource.objects.create(
            guide=matching,
            resource_type=RepairGuideResource.TYPE_TOOL,
            name='Precision screwdriver',
        )
        advanced = self.create_guide(slug='advanced-long-guide')
        advanced.difficulty = RepairGuide.DIFFICULTY_ADVANCED
        advanced.save(update_fields=('difficulty',))
        response = self.client.get(
            reverse('repair_guides:category', args=(self.category.slug,)),
            {
                'q': 'battery',
                'difficulty': RepairGuide.DIFFICULTY_BEGINNER,
                'max_minutes': '30',
                'resource': RepairGuideResource.TYPE_TOOL,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.title)
        self.assertNotContains(response, 'Advanced Long Guide')

    def test_only_contributors_can_submit_guides(self):
        url = reverse('repair_guides:guide_new')
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_contributor_can_submit_a_guide_with_numbered_steps_for_review(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse('repair_guides:guide_new'),
            {
                'category': self.category.pk,
                'title': 'Phone Port Inspection',
                'slug': 'phone-port-inspection',
                'summary': 'A safe external inspection guide.',
                'item_type': 'Phone',
                'difficulty': RepairGuide.DIFFICULTY_BEGINNER,
                'estimated_minutes': '10',
                'steps-TOTAL_FORMS': '1',
                'steps-INITIAL_FORMS': '0',
                'steps-MIN_NUM_FORMS': '1',
                'steps-MAX_NUM_FORMS': '30',
                'steps-0-position': '1',
                'steps-0-title': 'Inspect without opening',
                'steps-0-instructions': 'Disconnect power and inspect externally.',
                'resources-TOTAL_FORMS': '1',
                'resources-INITIAL_FORMS': '0',
                'resources-MIN_NUM_FORMS': '0',
                'resources-MAX_NUM_FORMS': '50',
                'resources-0-resource_type': '',
                'resources-0-name': '',
                'resources-0-quantity': '',
                'resources-0-product': '',
                'resources-0-position': '0',
            },
        )
        self.assertEqual(response.status_code, 302, response.content.decode())

        guide = RepairGuide.objects.get(slug='phone-port-inspection')
        self.assertRedirects(
            response,
            reverse('repair_guides:guide', args=(guide.slug,)),
        )
        self.assertEqual(guide.author, self.contributor)
        self.assertEqual(guide.status, RepairGuide.STATUS_SUBMITTED)
        self.assertEqual(guide.steps.count(), 1)

    def test_customer_can_submit_a_question_for_moderation(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse('repair_guides:question_new'),
            {
                'category': self.category.pk,
                'title': 'Can I clean the charging port?',
                'body': 'What is a safe external cleaning method?',
                'subcategory': '',
                'related_guide': '',
                'related_product': '',
            },
        )

        question = RepairQuestion.objects.get(title='Can I clean the charging port?')
        self.assertRedirects(
            response,
            reverse('repair_guides:question', args=(question.pk,)),
        )
        self.assertEqual(question.author, self.other_user)
        self.assertEqual(question.status, RepairQuestion.STATUS_PENDING)

    def test_question_image_validation_rejects_non_image_uploads(self):
        form = RepairQuestionForm(
            data={
                'category': self.category.pk,
                'title': 'Invalid image test',
                'body': 'This should not accept an invalid image.',
                'subcategory': '',
                'related_guide': '',
                'related_product': '',
            },
            files={
                'image': SimpleUploadedFile(
                    'not-an-image.png',
                    b'not an image',
                    content_type='image/png',
                ),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_staff_moderation_publishes_and_records_an_audit_event(self):
        guide = self.create_guide(
            slug='submitted-guide',
            status=RepairGuide.STATUS_SUBMITTED,
        )
        url = reverse(
            'repair_guides:moderate_content',
            args=('guide', guide.pk),
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            url,
            {'decision': RepairGuide.STATUS_PUBLISHED, 'note': ''},
        )

        guide.refresh_from_db()
        self.assertRedirects(response, reverse('repair_guides:moderation'))
        self.assertEqual(guide.status, RepairGuide.STATUS_PUBLISHED)
        self.assertEqual(guide.reviewer, self.staff)
        event = ContentModerationEvent.objects.get(guide=guide)
        self.assertEqual(event.previous_status, RepairGuide.STATUS_SUBMITTED)
        self.assertEqual(event.new_status, RepairGuide.STATUS_PUBLISHED)

    def test_staff_cannot_publish_a_guide_without_repair_steps(self):
        guide = self.create_guide(
            slug='guide-missing-steps',
            status=RepairGuide.STATUS_SUBMITTED,
        )
        guide.steps.all().delete()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                'repair_guides:moderate_content',
                args=('guide', guide.pk),
            ),
            {'decision': RepairGuide.STATUS_PUBLISHED},
        )

        guide.refresh_from_db()
        self.assertRedirects(response, reverse('repair_guides:moderation'))
        self.assertEqual(guide.status, RepairGuide.STATUS_SUBMITTED)
        self.assertFalse(
            ContentModerationEvent.objects.filter(guide=guide).exists()
        )

    def test_only_staff_can_open_the_moderation_queue(self):
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse('repair_guides:moderation')).status_code,
            403,
        )
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get(reverse('repair_guides:moderation')).status_code,
            200,
        )

    def test_pending_questions_are_private_until_staff_publication(self):
        question = self.create_question(status=RepairQuestion.STATUS_PENDING)
        url = reverse('repair_guides:question', args=(question.pk,))

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse(
                'repair_guides:moderate_content',
                args=('question', question.pk),
            ),
            {'decision': RepairQuestion.STATUS_PUBLISHED},
        )

        question.refresh_from_db()
        self.assertRedirects(response, reverse('repair_guides:moderation'))
        self.assertEqual(question.status, RepairQuestion.STATUS_PUBLISHED)
        self.assertTrue(ContentModerationEvent.objects.filter(
            question=question,
            new_status=RepairQuestion.STATUS_PUBLISHED,
        ).exists())

    def test_question_owner_can_edit_but_other_users_cannot(self):
        question = self.create_question(status=RepairQuestion.STATUS_PENDING)
        url = reverse('repair_guides:question_edit', args=(question.pk,))
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_contributor_answers_are_pending_and_customers_cannot_answer(self):
        question = self.create_question()
        url = reverse('repair_guides:question', args=(question.pk,))
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.post(url, {'body': 'Try this.'}).status_code, 403)

        self.client.force_login(self.contributor)
        response = self.client.post(url, {'body': 'Check the charging cable first.'})

        self.assertRedirects(response, url)
        answer = RepairAnswer.objects.get(question=question)
        self.assertEqual(answer.author, self.contributor)
        self.assertEqual(answer.status, RepairAnswer.STATUS_PENDING)

    def test_staff_can_publish_a_contributor_answer_with_audit(self):
        question = self.create_question()
        answer = RepairAnswer.objects.create(
            question=question,
            author=self.contributor,
            body='Check the power source before continuing.',
            status=RepairAnswer.STATUS_PENDING,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                'repair_guides:moderate_content',
                args=('answer', answer.pk),
            ),
            {'decision': RepairAnswer.STATUS_PUBLISHED},
        )

        answer.refresh_from_db()
        self.assertRedirects(response, reverse('repair_guides:moderation'))
        self.assertEqual(answer.status, RepairAnswer.STATUS_PUBLISHED)
        self.assertTrue(
            ContentModerationEvent.objects.filter(
                answer=answer,
                previous_status=RepairAnswer.STATUS_PENDING,
                new_status=RepairAnswer.STATUS_PUBLISHED,
            ).exists()
        )

    def test_helpful_feedback_is_upserted_and_report_is_moderated(self):
        guide = self.create_guide(slug='guide-with-feedback')
        feedback_url = reverse(
            'repair_guides:guide_feedback',
            args=(guide.slug,),
        )
        self.client.force_login(self.other_user)
        self.client.post(feedback_url, {'helpful': 'yes'})
        self.client.post(feedback_url, {'helpful': 'no'})
        self.assertEqual(guide.feedback.count(), 1)
        self.assertFalse(guide.feedback.get().is_helpful)

        self.client.post(
            reverse('repair_guides:guide_report', args=(guide.slug,)),
            {'reason': 'The steps need a safety clarification.'},
        )
        report = ContentReport.objects.get(guide=guide)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('repair_guides:moderate_report', args=(report.pk,)),
            {
                'decision': ContentReport.STATUS_RESOLVED,
                'note': 'Reviewed and escalated.',
            },
        )

        report.refresh_from_db()
        self.assertRedirects(response, reverse('repair_guides:moderation'))
        self.assertEqual(report.status, ContentReport.STATUS_RESOLVED)
        self.assertEqual(report.moderator, self.staff)
        self.assertIsNotNone(report.resolved_at)

    def test_answer_votes_are_saved_once_per_user(self):
        question = self.create_question()
        answer = RepairAnswer.objects.create(
            question=question,
            author=self.contributor,
            body='Check the charger and cable.',
            status=RepairAnswer.STATUS_PUBLISHED,
            reviewer=self.staff,
        )
        self.client.force_login(self.other_user)
        url = reverse('repair_guides:answer_vote', args=(answer.pk,))
        self.client.post(url, {'helpful': 'yes'})
        self.client.post(url, {'helpful': 'no'})

        self.assertEqual(answer.votes.count(), 1)
        self.assertFalse(answer.votes.get().is_helpful)
