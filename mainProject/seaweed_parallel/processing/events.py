import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from ..models import ClassificationBatch, ClassificationResult


logger = logging.getLogger(__name__)


def batch_group_name(batch_id):
	return f'classification_batch_{batch_id}'


def build_batch_progress(batch_id, result_id=None):
	batch = ClassificationBatch.objects.get(pk=batch_id)
	results = batch.results.all()
	current_result = results.filter(pk=result_id).first() if result_id else None
	return {
		'event': 'classification_progress',
		'batch_id': batch.id,
		'total': batch.total_images,
		'queued': results.filter(status=ClassificationResult.Status.QUEUED).count(),
		'processing': results.filter(status=ClassificationResult.Status.PROCESSING).count(),
		'completed': results.filter(status=ClassificationResult.Status.COMPLETED).count(),
		'failed': results.filter(status=ClassificationResult.Status.FAILED).count(),
		'batch_status': batch.status,
		'result_id': current_result.id if current_result else None,
		'worker': current_result.worker_name if current_result else '',
		'node': current_result.node_name if current_result else '',
		'prediction': current_result.predicted_class if current_result else '',
		'confidence': current_result.confidence if current_result else None,
		'processing_time': current_result.processing_time if current_result else None,
		'result_status': current_result.status if current_result else '',
	}


def publish_batch_progress(batch_id, result_id=None):
	try:
		payload = build_batch_progress(batch_id, result_id)
		channel_layer = get_channel_layer()
		async_to_sync(channel_layer.group_send)(
			batch_group_name(batch_id),
			{
				'type': 'classification.progress',
				'payload': payload,
			},
		)
	except Exception:
		logger.exception('Unable to publish progress for batch %s', batch_id)