import os
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings


@contextmanager
def classification_db_lock():
	lock_path = Path(settings.BASE_DIR) / '.classification-db.lock'
	lock_path.touch(exist_ok=True)
	with lock_path.open('a+b') as lock_file:
		if os.name == 'nt':
			import msvcrt

			lock_file.seek(0)
			msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
			try:
				yield
			finally:
				lock_file.seek(0)
				msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
		else:
			import fcntl

			fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
			try:
				yield
			finally:
				fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)