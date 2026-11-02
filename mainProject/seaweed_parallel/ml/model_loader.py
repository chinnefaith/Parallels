from functools import lru_cache
from pathlib import Path

import tensorflow as tf
from django.conf import settings


MODEL_PATH = Path(settings.BASE_DIR) / 'seaweed_parallel' / 'model' / 'shell_model.tflite'


@lru_cache(maxsize=1)
def get_interpreter():
	"""Load one interpreter per worker process and reuse it for later tasks."""
	interpreter = tf.lite.Interpreter(model_path=str(MODEL_PATH))
	interpreter.allocate_tensors()
	return interpreter