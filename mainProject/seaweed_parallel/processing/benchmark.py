import time
from pathlib import Path

from django.core.files import File

from ..models import (
	BenchmarkMeasurement,
	BenchmarkRun,
	ClassificationBatch,
	ClassificationResult,
)
from ..ml.classifier import classify_image as run_classifier
from .tasks import classify_image


def _metrics(image_count, worker_count, total_time, inference_times, task_times, speedup):
	return {
		'image_count': image_count,
		'worker_count': worker_count,
		'total_processing_time': total_time,
		'average_inference_time': (
			sum(inference_times) / len(inference_times)
			if inference_times else 0.0
		),
		'average_task_time': (
			sum(task_times) / len(task_times)
			if task_times else 0.0
		),
		'throughput': image_count / total_time if total_time else 0.0,
		'speedup': speedup,
		'efficiency': speedup / worker_count if worker_count else 0.0,
	}


def measure_sequential(image_paths):
	image_paths = [Path(path) for path in image_paths]
	inference_times = []
	task_times = []
	started_at = time.perf_counter()
	for image_path in image_paths:
		task_started_at = time.perf_counter()
		inference_started_at = time.perf_counter()
		run_classifier(image_path)
		inference_times.append(time.perf_counter() - inference_started_at)
		task_times.append(time.perf_counter() - task_started_at)
	total_time = time.perf_counter() - started_at
	return _metrics(
		len(image_paths), 1, total_time,
		inference_times, task_times, 1.0,
	)


def _create_parallel_batch(user, image_paths):
	batch = ClassificationBatch.objects.create(
		user=user,
		total_images=len(image_paths),
	)
	results = []
	for image_path in image_paths:
		result = ClassificationResult(batch=batch)
		with Path(image_path).open('rb') as image_file:
			result.image.save(Path(image_path).name, File(image_file), save=True)
		results.append(result)
	return batch, results


def measure_parallel(user, image_paths, worker_count, timeout=1800):
	image_paths = [Path(path) for path in image_paths]
	batch, results = _create_parallel_batch(user, image_paths)
	queue = f'benchmark-{worker_count}'
	started_at = time.perf_counter()
	async_results = [
		classify_image.apply_async(args=[result.pk], queue=queue)
		for result in results
	]
	for async_result in async_results:
		async_result.get(timeout=timeout, propagate=False)
	total_time = time.perf_counter() - started_at
	results = list(batch.results.all())
	return _metrics(
		len(results), worker_count, total_time,
		[result.model_inference_time for result in results if result.model_inference_time is not None],
		[result.processing_time for result in results if result.processing_time is not None],
		0.0,
	), batch


def run_benchmark(user, image_paths, worker_count, timeout=1800):
	image_paths = [Path(path) for path in image_paths]
	if not image_paths:
		raise ValueError('At least one image is required.')
	if worker_count not in (2, 4, 6):
		raise ValueError('worker_count must be 2, 4, or 6.')

	run = BenchmarkRun.objects.create(
		user=user,
		image_count=len(image_paths),
	)
	try:
		sequential = measure_sequential(image_paths)
		BenchmarkMeasurement.objects.create(
			run=run,
			mode='SEQUENTIAL',
			**sequential,
		)
		parallel, batch = measure_parallel(
			user, image_paths, worker_count, timeout=timeout,
		)
		parallel['speedup'] = (
			sequential['total_processing_time'] /
			parallel['total_processing_time']
			if parallel['total_processing_time'] else 0.0
		)
		parallel['efficiency'] = parallel['speedup'] / worker_count
		BenchmarkMeasurement.objects.create(
			run=run,
			mode='PARALLEL',
			**parallel,
		)
		run.status = BenchmarkRun.Status.COMPLETED
		run.save(update_fields=['status'])
		return run, batch
	except Exception as exc:
		run.status = BenchmarkRun.Status.FAILED
		run.error_message = 'Benchmark execution failed.'
		run.save(update_fields=['status', 'error_message'])
		raise