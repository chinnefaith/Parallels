from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
	BenchmarkMeasurement,
	BenchmarkRun,
	ClassificationBatch,
	ClassificationResult,
	User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
		('User metadata', {'fields': ('created_at',)}),
	)
	readonly_fields = ('created_at',)


@admin.register(ClassificationBatch)
class ClassificationBatchAdmin(admin.ModelAdmin):
	list_display = (
		'id', 'user', 'status', 'total_images',
		'completed_images', 'failed_images', 'created_at',
	)
	list_filter = ('status', 'created_at')
	search_fields = ('user__username',)


@admin.register(ClassificationResult)
class ClassificationResultAdmin(admin.ModelAdmin):
	list_display = (
		'id', 'batch', 'status', 'predicted_class',
		'confidence', 'worker_name', 'node_name',
	)
	list_filter = ('status', 'node_name')
	search_fields = ('batch__user__username', 'predicted_class')


@admin.register(BenchmarkRun)
class BenchmarkRunAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'image_count', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('user__username',)


@admin.register(BenchmarkMeasurement)
class BenchmarkMeasurementAdmin(admin.ModelAdmin):
	list_display = (
		'run', 'mode', 'worker_count', 'image_count',
		'total_processing_time', 'throughput', 'speedup', 'efficiency',
	)
	list_filter = ('mode', 'worker_count')
