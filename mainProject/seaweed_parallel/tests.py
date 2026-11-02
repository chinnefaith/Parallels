import json
import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tensorflow as tf
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import User
from .models import ClassificationBatch, ClassificationResult
from .consumers import ClassificationProgressConsumer
from .processing.events import batch_group_name
from .processing.benchmark import _metrics
from .processing.tasks import classify_image


class AuthenticationTests(TestCase):
	def setUp(self):
		self.password = 'Strong-password-123'
		self.user = get_user_model().objects.create_user(
			username='existing-user',
			password=self.password,
		)

	def test_dashboard_requires_authentication(self):
		response = self.client.get(reverse('dashboard'))

		self.assertRedirects(
			response,
			f'{reverse("signin")}?next={reverse("dashboard")}',
		)

	def test_shell_quiz_requires_authentication_and_renders_quiz_assets(self):
		response = self.client.get(reverse('shell_quiz'))

		self.assertRedirects(
			response,
			f'{reverse("signin")}?next={reverse("shell_quiz")}',
		)

		self.client.force_login(self.user)
		response = self.client.get(reverse('shell_quiz'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'data-quiz-url="/static/quiz/shell_quiz.json"')
		self.assertContains(response, 'data-image-base="/static/quiz/images/"')
		self.assertContains(response, 'js/quiz.js')
		self.assertContains(response, 'id="quiz-progress"')
		self.assertContains(response, 'id="quiz-hint"')
		self.assertContains(response, 'id="quiz-title"')
		self.assertContains(response, 'Play another random quiz')
		self.assertNotContains(response, 'id="quiz-category"')
		self.assertNotContains(response, 'Choose your quiz')

	def test_shells_library_renders_shells_by_category(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('shells_library'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['shell_count'], 39)
		self.assertEqual(len(response.context['categories']), 3)
		self.assertEqual(
			sum(len(category['shells']) for category in response.context['categories']),
			39,
		)
		self.assertEqual(response.content.count(b'class="shell-card"'), 39)
		self.assertEqual(response.content.count(b'class="shell-card" href="/shells-library/'), 39)
		category_names = {
			category['name'] for category in response.context['categories']
		}
		self.assertNotIn('Cephalopods', category_names)
		self.assertNotIn('Scaphopods', category_names)
		self.assertNotContains(response, 'Cephalopod')
		self.assertNotContains(response, 'Scaphopod')
		self.assertContains(response, '/static/shell-categories/Bivalves.png')
		self.assertContains(response, 'class="category-filter-label"')
		self.assertContains(response, 'data-category-filter="all"')
		self.assertContains(response, 'data-category-filter="bivalve"')
		self.assertContains(response, 'js/shells-library.js')
		self.assertContains(response, '/shells-library/0/')
		self.assertNotContains(response, 'href="#category-')
		self.assertNotContains(response, 'class="category-heading"')
		self.assertContains(response, 'Lapas/Kapinan')
		self.assertContains(response, 'class="shell-card"')

	def test_shell_detail_shows_reference_fields_and_related_shells(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('shell_detail', args=[0]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['shell']['basic_identification']['common_name'], 'Lapas/Kapinan')
		self.assertEqual(response.context['category_name'], 'Gastropod')
		self.assertEqual(len(response.context['shell']['habitat_fields']), 5)
		self.assertNotIn(
			'Habitat',
			[section['title'] for section in response.context['shell']['detail_sections']],
		)
		self.assertEqual(len(response.context['related_shells']), 4)
		self.assertTrue(all(
			related['basic_identification']['classification'] == 'Gastropod'
			and related['id'] != 0
			for related in response.context['related_shells']
		))
		for label in ('Identification', 'Appearance', 'Habitat', 'Edibility and safety', 'Similar species'):
			self.assertContains(response, label)
		self.assertContains(response, 'Highly prized delicacy')
		self.assertContains(response, 'habitat-summary')
		self.assertContains(response, 'Rocky intertidal and sublittoral ocean reefs')
		self.assertContains(response, '/shells-library/')

	def test_shell_detail_returns_not_found_for_invalid_or_hidden_shell(self):
		self.client.force_login(self.user)

		self.assertEqual(
			self.client.get(reverse('shell_detail', args=[999])).status_code,
			404,
		)

		shell_records = json.loads(
			(Path(__file__).resolve().parent.parent
			 / 'static' / 'shell-categories' / 'shell.json').read_text(
				 encoding='utf-8'
			 )
		)
		cephalopod_id = next(
			index for index, record in enumerate(shell_records)
			if record['basic_identification']['classification'].strip().casefold() == 'cephalopod'
		)
		self.assertEqual(
			self.client.get(reverse('shell_detail', args=[cephalopod_id])).status_code,
			404,
		)

	def test_about_us_page_requires_authentication_and_shows_reference_content(self):
		response = self.client.get(reverse('about_us'))

		self.assertRedirects(
			response,
			f'{reverse("signin")}?next={reverse("about_us")}',
		)

		self.client.force_login(self.user)
		response = self.client.get(reverse('about_us'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'AI-powered shell identification and classification workspace.')
		self.assertContains(response, 'What Seastem does')
		self.assertContains(response, 'How the system works')
		self.assertContains(response, 'Built for parallel processing')
		self.assertContains(response, 'System limitations')
		self.assertContains(response, 'css/about.css')
		self.assertContains(response, 'href="/dashboard/"')

	def test_signin_uses_configured_logo(self):
		response = self.client.get(reverse('signin'))

		self.assertContains(response, 'src="/static/images/logo.png"')
		self.assertContains(response, 'class="scan-sweep"')
		self.assertContains(response, 'href="/signup/"')
		self.assertContains(response, 'aria-label="Show password"')
		self.assertContains(response, 'aria-controls="password"')
		self.assertContains(response, 'class="eye-closed-icon"')

	def test_user_can_sign_in_and_sign_out(self):
		response = self.client.post(reverse('signin'), {
			'username': self.user.username,
			'password': self.password,
		})

		self.assertRedirects(response, reverse('dashboard'))
		self.assertTrue(response.wsgi_request.user.is_authenticated)
		self.assertContains(self.client.get(reverse('dashboard')), self.user.username)

		response = self.client.post(reverse('signout'))
		self.assertRedirects(response, reverse('signin'))
		self.assertRedirects(
			self.client.get(reverse('dashboard')),
			f'{reverse("signin")}?next={reverse("dashboard")}',
		)

	def test_invalid_credentials_do_not_sign_in(self):
		response = self.client.post(reverse('signin'), {
			'username': self.user.username,
			'password': 'wrong-password',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Invalid username or password.')
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_sign_in_ignores_external_next_url(self):
		response = self.client.post(
			f'{reverse("signin")}?next=https://example.com',
			{
				'username': self.user.username,
				'password': self.password,
			},
		)

		self.assertRedirects(response, reverse('dashboard'))

	def test_user_can_sign_up(self):
		response = self.client.post(reverse('signup'), {
			'username': 'new-user',
			'password1': 'Another-strong-password-123',
			'password2': 'Another-strong-password-123',
		})

		self.assertRedirects(response, reverse('signin'))
		self.assertTrue(
			get_user_model().objects.filter(username='new-user').exists()
		)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_signup_page_uses_shared_auth_design(self):
		response = self.client.get(reverse('signup'))

		self.assertContains(response, 'css/signin.css')
		self.assertContains(response, 'src="/static/images/logo.png"')
		self.assertContains(response, 'aria-controls="id_password1"')
		self.assertContains(response, 'aria-controls="id_password2"')
		self.assertContains(response, 'class="eye-closed-icon"')

	def test_authentication_uses_project_user_model(self):
		self.assertIs(get_user_model(), User)
		self.assertIsNotNone(self.user.created_at)


class ClassificationTaskTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='classifier-user',
			password='Strong-password-123',
		)

	def create_image(self, name='sample.png'):
		image_data = io.BytesIO()
		Image.new('RGB', (224, 224), color=(40, 120, 80)).save(
			image_data,
			format='PNG',
		)
		return SimpleUploadedFile(
			name,
			image_data.getvalue(),
			content_type='image/png',
		)

	def test_one_image_task_classifies_and_updates_batch(self):
		batch = ClassificationBatch.objects.create(
			user=self.user,
			total_images=1,
		)
		result = ClassificationResult.objects.create(
			batch=batch,
			image=self.create_image(),
		)

		with patch.dict(os.environ, {'SEAWEED_NODE_NAME': 'NODE_TEST'}):
			task_result = classify_image.apply(args=[result.pk])

		result.refresh_from_db()
		batch.refresh_from_db()
		self.assertEqual(task_result.result['node_name'], 'NODE_TEST')
		self.assertTrue(task_result.result['worker_name'])
		self.assertEqual(result.status, ClassificationResult.Status.COMPLETED)
		self.assertTrue(result.predicted_class)
		self.assertIsNotNone(result.confidence)
		self.assertGreaterEqual(result.processing_time, 0)
		self.assertEqual(batch.status, ClassificationBatch.Status.COMPLETED)
		self.assertEqual(batch.completed_images, 1)
		self.assertEqual(batch.failed_images, 0)

	def test_failed_image_task_updates_only_its_result_and_batch(self):
		batch = ClassificationBatch.objects.create(
			user=self.user,
			total_images=1,
		)
		result = ClassificationResult.objects.create(
			batch=batch,
			image='classification_images/missing.png',
		)

		task_result = classify_image.apply(args=[result.pk])

		result.refresh_from_db()
		batch.refresh_from_db()
		self.assertEqual(task_result.result['status'], ClassificationResult.Status.FAILED)
		self.assertEqual(result.status, ClassificationResult.Status.FAILED)
		self.assertEqual(result.error_message, 'Image classification failed.')
		self.assertGreaterEqual(result.processing_time, 0)
		self.assertEqual(batch.status, ClassificationBatch.Status.FAILED)
		self.assertEqual(batch.completed_images, 0)
		self.assertEqual(batch.failed_images, 1)


class MultiImageUploadTests(TestCase):
	def setUp(self):
		self.media_root = tempfile.TemporaryDirectory()
		self.media_override = override_settings(MEDIA_ROOT=self.media_root.name)
		self.media_override.enable()
		self.user = get_user_model().objects.create_user(
			username='upload-user',
			password='Strong-password-123',
		)
		self.client.force_login(self.user)

	def tearDown(self):
		self.media_override.disable()
		self.media_root.cleanup()

	def create_image(self, name):
		image_data = io.BytesIO()
		Image.new('RGB', (224, 224), color=(40, 120, 80)).save(
			image_data,
			format='PNG',
		)
		return SimpleUploadedFile(
			name,
			image_data.getvalue(),
			content_type='image/png',
		)

	def test_five_images_create_five_results_and_five_tasks(self):
		images = [self.create_image(f'image-{index}.png') for index in range(5)]

		with patch('seaweed_parallel.views.classify_image.delay') as enqueue:
			response = self.client.post(reverse('dashboard'), {'images': images})

		self.assertRedirects(response, reverse('dashboard'))
		batch = ClassificationBatch.objects.get(user=self.user)
		results = list(batch.results.order_by('id'))
		self.assertEqual(batch.total_images, 5)
		self.assertEqual(len(results), 5)
		self.assertEqual(enqueue.call_count, 5)
		self.assertEqual(
			[call.args[0] for call in enqueue.call_args_list],
			[result.pk for result in results],
		)

	def test_invalid_upload_creates_no_batch_or_task(self):
		invalid_file = SimpleUploadedFile(
			'not-an-image.txt',
			b'not image data',
			content_type='text/plain',
		)

		with patch('seaweed_parallel.views.classify_image.delay') as enqueue:
			response = self.client.post(
				reverse('dashboard'),
				{'images': [invalid_file]},
			)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'not a valid image file')
		self.assertFalse(ClassificationBatch.objects.exists())
		enqueue.assert_not_called()


@override_settings(CHANNEL_LAYERS={
	'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
})
class ClassificationWebsocketTests(TransactionTestCase):
	def setUp(self):
		self.owner = get_user_model().objects.create_user(username='owner')
		self.other_user = get_user_model().objects.create_user(username='other')
		self.batch = ClassificationBatch.objects.create(
			user=self.owner,
			total_images=1,
		)

	def communicator_for(self, user, batch_id):
		consumer_application = ClassificationProgressConsumer.as_asgi()

		async def authenticated_application(scope, receive, send):
			scope = dict(scope)
			scope['user'] = user
			scope['url_route'] = {'kwargs': {'batch_id': batch_id}}
			return await consumer_application(scope, receive, send)

		return WebsocketCommunicator(
			authenticated_application,
			f'/ws/classification/{batch_id}/',
		)

	def test_owner_receives_progress_event(self):
		communicator = self.communicator_for(self.owner, self.batch.pk)

		async def exercise():
			connected, _ = await communicator.connect()
			self.assertTrue(connected)
			initial_event = await communicator.receive_json_from()
			self.assertEqual(initial_event['batch_id'], self.batch.pk)
			await get_channel_layer().group_send(
				batch_group_name(self.batch.pk),
				{
					'type': 'classification.progress',
					'payload': {
						'event': 'classification_progress',
						'batch_id': self.batch.pk,
						'total': 1,
						'queued': 0,
						'processing': 0,
						'completed': 1,
						'failed': 0,
						'batch_status': 'COMPLETED',
						'result_id': None,
					},
				},
			)
			event = await communicator.receive_json_from()
			await communicator.disconnect()
			return event

		event = async_to_sync(exercise)()
		self.assertEqual(event['batch_id'], self.batch.pk)
		self.assertEqual(event['completed'], 1)

	def test_other_user_cannot_subscribe_to_batch(self):
		communicator = self.communicator_for(self.other_user, self.batch.pk)

		connected, close_code = async_to_sync(communicator.connect)()
		self.assertFalse(connected)
		self.assertEqual(close_code, 4403)


class BenchmarkMetricTests(TestCase):
	def test_speedup_and_efficiency_are_derived_from_measured_time(self):
		metrics = _metrics(
			image_count=10,
			worker_count=2,
			total_time=5.0,
			inference_times=[0.4, 0.6],
			task_times=[0.5, 0.7],
			speedup=2.0,
		)

		self.assertEqual(metrics['throughput'], 2.0)
		self.assertEqual(metrics['efficiency'], 1.0)


class BenchmarkPageTests(TestCase):
	def test_authenticated_benchmark_page_renders(self):
		user = get_user_model().objects.create_user(username='benchmark-user')
		self.client.force_login(user)

		response = self.client.get(reverse('benchmark'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Benchmark results')
		self.assertContains(response, 'No benchmark measurements recorded yet')


class PreprocessingAlignmentTests(TestCase):
	def test_preprocess_image_matches_efficientnet_v2_training_pipeline(self):
		with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as image_file:
			Image.new('RGB', (64, 64), color=(12, 34, 56)).save(image_file.name)
			image_path = image_file.name

		try:
			from .ml.preprocessing import preprocess_image

			processed = preprocess_image(image_path)
			with Image.open(image_path) as image:
				rgb = image.convert('RGB').resize((224, 224))
				expected = np.asarray(rgb, dtype=np.float32)
				expected = tf.keras.applications.efficientnet_v2.preprocess_input(expected)
				expected = np.expand_dims(expected, axis=0).astype(np.float32)

			self.assertEqual(processed.shape, (1, 224, 224, 3))
			self.assertEqual(processed.dtype, np.float32)
			np.testing.assert_allclose(processed, expected, rtol=1e-6, atol=1e-6)
		finally:
			os.unlink(image_path)


class HistoryPageTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='history-user')
		self.other_user = get_user_model().objects.create_user(username='other-history-user')
		self.client.force_login(self.user)
		ClassificationBatch.objects.create(user=self.user, total_images=1)
		ClassificationBatch.objects.create(user=self.user, total_images=2)
		ClassificationBatch.objects.create(user=self.other_user, total_images=3)

	def test_dashboard_shows_latest_batch_only_but_counts_all_history(self):
		batch_1 = ClassificationBatch.objects.create(user=self.user, total_images=1)
		batch_2 = ClassificationBatch.objects.create(user=self.user, total_images=2)
		ClassificationResult.objects.create(batch=batch_1, image=SimpleUploadedFile('first.png', b'img1', content_type='image/png'))
		ClassificationResult.objects.create(batch=batch_2, image=SimpleUploadedFile('second.png', b'img2', content_type='image/png'))
		ClassificationResult.objects.create(batch=batch_2, image=SimpleUploadedFile('third.png', b'img3', content_type='image/png'))

		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.context['batches']), 1)
		self.assertContains(response, 'Classification results')
		self.assertContains(response, 'Batch 2')
		self.assertNotContains(response, 'Batch 1')
		self.assertEqual(response.context['overview']['total'], 3)

	def test_history_shows_all_owned_batches_only(self):
		response = self.client.get(reverse('history'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Batch 1')
		self.assertContains(response, 'Batch 2')
		self.assertNotContains(response, 'Batch 3')
		self.assertContains(response, 'nav-button is-active')

	def test_history_paginates_owned_batches(self):
		for index in range(10):
			ClassificationBatch.objects.create(user=self.user, total_images=index + 1)

		first_page = self.client.get(reverse('history'))
		second_page = self.client.get(reverse('history'), {'page': 2})

		self.assertEqual(first_page.status_code, 200)
		self.assertEqual(first_page.context['page_obj'].paginator.count, 12)
		self.assertEqual(len(first_page.context['batches']), 10)
		self.assertTrue(first_page.context['page_obj'].has_next())
		self.assertEqual(len(second_page.context['batches']), 2)
		self.assertFalse(second_page.context['page_obj'].has_next())
		self.assertContains(first_page, '?page=2')
