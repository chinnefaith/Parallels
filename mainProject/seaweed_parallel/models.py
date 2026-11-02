from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class User(AbstractUser):
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['username']


class ClassificationBatch(models.Model):
	class Status(models.TextChoices):
		QUEUED = 'QUEUED', 'Queued'
		PROCESSING = 'PROCESSING', 'Processing'
		COMPLETED = 'COMPLETED', 'Completed'
		PARTIAL = 'PARTIAL', 'Partial'
		FAILED = 'FAILED', 'Failed'

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='classification_batches',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	started_at = models.DateTimeField(null=True, blank=True)
	completed_at = models.DateTimeField(null=True, blank=True)
	total_images = models.PositiveIntegerField(default=0)
	completed_images = models.PositiveIntegerField(default=0)
	failed_images = models.PositiveIntegerField(default=0)
	status = models.CharField(
		max_length=16,
		choices=Status.choices,
		default=Status.QUEUED,
	)
	total_processing_time = models.FloatField(null=True, blank=True)

	class Meta:
		ordering = ['-created_at']


class ClassificationResult(models.Model):
	class Status(models.TextChoices):
		QUEUED = 'QUEUED', 'Queued'
		PROCESSING = 'PROCESSING', 'Processing'
		COMPLETED = 'COMPLETED', 'Completed'
		FAILED = 'FAILED', 'Failed'

	batch = models.ForeignKey(
		ClassificationBatch,
		on_delete=models.CASCADE,
		related_name='results',
	)
	image = models.ImageField(upload_to='classification_images/%Y/%m/%d/')
	predicted_class = models.CharField(max_length=255, blank=True)
	confidence = models.FloatField(null=True, blank=True)
	processing_time = models.FloatField(null=True, blank=True)
	model_inference_time = models.FloatField(null=True, blank=True)
	worker_name = models.CharField(max_length=255, blank=True)
	node_name = models.CharField(max_length=100, blank=True)
	status = models.CharField(
		max_length=16,
		choices=Status.choices,
		default=Status.QUEUED,
	)
	error_message = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']


class BenchmarkRun(models.Model):
	class Status(models.TextChoices):
		COMPLETED = 'COMPLETED', 'Completed'
		FAILED = 'FAILED', 'Failed'

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='benchmark_runs',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	image_count = models.PositiveIntegerField()
	status = models.CharField(
		max_length=16,
		choices=Status.choices,
		default=Status.COMPLETED,
	)
	error_message = models.TextField(blank=True)

	class Meta:
		ordering = ['-created_at']


class BenchmarkMeasurement(models.Model):
	run = models.ForeignKey(
		BenchmarkRun,
		on_delete=models.CASCADE,
		related_name='measurements',
	)
	worker_count = models.PositiveIntegerField()
	mode = models.CharField(max_length=16)
	image_count = models.PositiveIntegerField()
	total_processing_time = models.FloatField()
	average_inference_time = models.FloatField()
	average_task_time = models.FloatField()
	throughput = models.FloatField()
	speedup = models.FloatField()
	efficiency = models.FloatField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['worker_count', 'created_at']
