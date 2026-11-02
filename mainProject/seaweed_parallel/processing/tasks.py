import logging
import time

from celery import shared_task
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from ..ml.classifier import classify_image as run_classifier
from ..models import ClassificationBatch, ClassificationResult
from .events import publish_batch_progress
from .db_lock import classification_db_lock
from .worker_utils import get_node_name, get_worker_name


logger = logging.getLogger(__name__)


def update_batch_status(batch_id):
	with classification_db_lock(), transaction.atomic():
		batch = ClassificationBatch.objects.select_for_update().get(pk=batch_id)
		results = batch.results.all()
		completed = results.filter(status=ClassificationResult.Status.COMPLETED).count()
		failed = results.filter(status=ClassificationResult.Status.FAILED).count()
		finished = completed + failed

		batch.completed_images = completed
		batch.failed_images = failed
		if batch.started_at is None and finished:
			batch.started_at = timezone.now()
		if finished == batch.total_images and batch.total_images:
			batch.completed_at = timezone.now()
			batch.total_processing_time = (
				batch.completed_at - batch.started_at
			).total_seconds() if batch.started_at else None
			batch.status = (
				ClassificationBatch.Status.COMPLETED
				if failed == 0 else (
					ClassificationBatch.Status.FAILED
					if completed == 0 else ClassificationBatch.Status.PARTIAL
				)
			)
		elif finished:
			batch.status = ClassificationBatch.Status.PROCESSING
		batch.save(update_fields=[
			'completed_images', 'failed_images', 'started_at',
			'completed_at', 'total_processing_time', 'status',
		])


@shared_task(
	bind=True,
	name='seaweed_parallel.classify_image',
	acks_late=True,
	 autoretry_for=(OperationalError,),
	retry_backoff=True,
	retry_kwargs={'max_retries': 5},
)
def classify_image(self, result_id):
	worker_name = get_worker_name(self.request)
	node_name = get_node_name()
	started_at = time.perf_counter()

	try:
		with classification_db_lock(), transaction.atomic():
			result = ClassificationResult.objects.select_related('batch').select_for_update().get(
				pk=result_id,
			)
			result.status = ClassificationResult.Status.PROCESSING
			result.worker_name = worker_name
			result.node_name = node_name
			result.batch.status = ClassificationBatch.Status.PROCESSING
			result.batch.started_at = result.batch.started_at or timezone.now()
			result.batch.save(update_fields=['status', 'started_at'])
			result.save(update_fields=['status', 'worker_name', 'node_name'])
		publish_batch_progress(result.batch_id, result.pk)

		inference_started_at = time.perf_counter()
		prediction = run_classifier(result.image.path)
		model_inference_time = time.perf_counter() - inference_started_at
		processing_time = time.perf_counter() - started_at

		with classification_db_lock(), transaction.atomic():
			result = ClassificationResult.objects.get(pk=result_id)
			result.predicted_class = prediction['predicted_class']
			result.confidence = prediction['confidence']
			result.processing_time = processing_time
			result.model_inference_time = model_inference_time
			result.status = ClassificationResult.Status.COMPLETED
			result.error_message = ''
			result.save(update_fields=[
				'predicted_class', 'confidence', 'processing_time',
				'model_inference_time', 'status', 'error_message',
			])

		update_batch_status(result.batch_id)
		publish_batch_progress(result.batch_id, result_id)
		logger.info(
			'[CLASSIFICATION] batch=%s result=%s node=%s worker=%s prediction=%s confidence=%.2f time=%.4fs',
			result.batch_id, result_id, node_name, worker_name,
			prediction['predicted_class'], prediction['confidence'], processing_time,
		)
		return prediction | {
			'processing_time': processing_time,
			'worker_name': worker_name,
			'node_name': node_name,
		}

	except OperationalError:
		logger.warning(
			'[CLASSIFICATION RETRY] batch result=%s worker=%s node=%s',
			result_id, worker_name, node_name,
		)
		raise
	except Exception as exc:
		processing_time = time.perf_counter() - started_at
		with classification_db_lock(), transaction.atomic():
			result = ClassificationResult.objects.get(pk=result_id)
			result.status = ClassificationResult.Status.FAILED
			result.worker_name = worker_name
			result.node_name = node_name
			result.processing_time = processing_time
			result.model_inference_time = None
			result.error_message = 'Image classification failed.'
			result.save(update_fields=[
				'status', 'worker_name', 'node_name',
				'processing_time', 'error_message',
				'model_inference_time',
			])
		update_batch_status(result.batch_id)
		publish_batch_progress(result.batch_id, result_id)
		logger.exception(
			'[CLASSIFICATION ERROR] batch=%s result=%s node=%s worker=%s error=%s',
			result.batch_id, result_id, node_name, worker_name, exc,
		)
		return {
			'status': ClassificationResult.Status.FAILED,
			'processing_time': processing_time,
			'worker_name': worker_name,
			'node_name': node_name,
		}