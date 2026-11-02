import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .processing.events import batch_group_name, build_batch_progress


@database_sync_to_async
def user_can_access_batch(user_id, batch_id):
	from .models import ClassificationBatch

	return ClassificationBatch.objects.filter(
		pk=batch_id,
		user_id=user_id,
	).exists()


@database_sync_to_async
def get_batch_snapshots(batch_id):
	from .models import ClassificationBatch

	batch = ClassificationBatch.objects.get(pk=batch_id)
	return [
		build_batch_progress(batch_id),
		*[build_batch_progress(batch_id, result.id) for result in batch.results.all()],
	]


class ClassificationProgressConsumer(AsyncJsonWebsocketConsumer):
	async def connect(self):
		user = self.scope.get('user')
		if not user or not user.is_authenticated:
			await self.close(code=4401)
			return

		self.batch_id = self.scope['url_route']['kwargs']['batch_id']
		if not await user_can_access_batch(user.id, self.batch_id):
			await self.close(code=4403)
			return

		self.group_name = batch_group_name(self.batch_id)
		await self.channel_layer.group_add(self.group_name, self.channel_name)
		await self.accept()
		await self.send_snapshots_once()
		self.snapshot_task = asyncio.create_task(self.send_snapshots())

	async def send_snapshots_once(self):
		for snapshot in await get_batch_snapshots(self.batch_id):
			await self.send_json(snapshot)

	async def send_snapshots(self):
		try:
			while True:
				await asyncio.sleep(1.5)
				await self.send_snapshots_once()
		except asyncio.CancelledError:
			return

	async def disconnect(self, close_code):
		if hasattr(self, 'snapshot_task'):
			self.snapshot_task.cancel()
		if hasattr(self, 'group_name'):
			await self.channel_layer.group_discard(self.group_name, self.channel_name)

	async def classification_progress(self, event):
		await self.send_json(event['payload'])