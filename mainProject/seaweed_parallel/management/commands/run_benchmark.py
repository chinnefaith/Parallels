from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from seaweed_parallel.processing.benchmark import run_benchmark


class Command(BaseCommand):
	help = 'Measure sequential and Celery parallel classification performance.'

	def add_arguments(self, parser):
		parser.add_argument('--username', required=True)
		parser.add_argument('--image', action='append', required=True)
		parser.add_argument('--workers', type=int, choices=(2, 4, 6), required=True)
		parser.add_argument('--timeout', type=int, default=1800)

	def handle(self, *args, **options):
		user = get_user_model().objects.filter(
			username=options['username'],
		).first()
		if user is None:
			raise CommandError(f"User not found: {options['username']}")
		image_paths = [Path(path) for path in options['image']]
		missing = [str(path) for path in image_paths if not path.is_file()]
		if missing:
			raise CommandError(f'Image file not found: {missing[0]}')

		try:
			run, batch = run_benchmark(
				user,
				image_paths,
				options['workers'],
				timeout=options['timeout'],
			)
		except Exception as exc:
			raise CommandError(str(exc)) from exc

		self.stdout.write(self.style.SUCCESS(
			f'Benchmark run={run.pk} completed; parallel batch={batch.pk}'
		))
		for measurement in run.measurements.all():
			self.stdout.write(
				f'{measurement.mode} workers={measurement.worker_count} '
				f'total={measurement.total_processing_time:.4f}s '
				f'average_inference={measurement.average_inference_time:.4f}s '
				f'throughput={measurement.throughput:.4f}/s '
				f'speedup={measurement.speedup:.4f} '
				f'efficiency={measurement.efficiency:.4f}'
			)