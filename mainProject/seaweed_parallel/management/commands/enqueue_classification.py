from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from seaweed_parallel.models import ClassificationBatch, ClassificationResult
from seaweed_parallel.processing.tasks import classify_image


class Command(BaseCommand):
	help = 'Create one image result and enqueue one classification task.'

	def add_arguments(self, parser):
		parser.add_argument('--username', required=True)
		parser.add_argument('--image', required=True, type=Path)

	def handle(self, *args, **options):
		username = options['username']
		image_path = options['image']
		user = get_user_model().objects.filter(username=username).first()
		if user is None:
			raise CommandError(f'User not found: {username}')
		if not image_path.is_file():
			raise CommandError(f'Image file not found: {image_path}')

		batch = ClassificationBatch.objects.create(
			user=user,
			total_images=1,
		)
		with image_path.open('rb') as image_file:
			result = ClassificationResult(batch=batch)
			result.image.save(image_path.name, File(image_file), save=True)

		task = classify_image.delay(result.pk)
		self.stdout.write(self.style.SUCCESS(
			f'Queued task_id={task.id} batch_id={batch.pk} result_id={result.pk}'
		))