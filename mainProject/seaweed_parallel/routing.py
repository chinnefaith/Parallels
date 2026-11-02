from django.urls import re_path

from .consumers import ClassificationProgressConsumer


websocket_urlpatterns = [
	re_path(
		r'^ws/classification/(?P<batch_id>[0-9]+)/$',
		ClassificationProgressConsumer.as_asgi(),
	),
]
