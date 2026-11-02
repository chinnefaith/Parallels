import logging
from pathlib import Path
from typing import Union

import numpy as np
import tensorflow as tf
from PIL import Image


logger = logging.getLogger(__name__)
IMAGE_SIZE = (224, 224)


def preprocess_for_model(image_or_path: Union[str, Path, Image.Image], *, logger_obj=None):
	"""Align the Django prediction pipeline with the training pipeline.

	The training pipeline used:
	- PIL decode -> RGB
	- resize to (224, 224)
	- convert to float32
	- efficientnet_v2.preprocess_input
	- add batch dimension
	"""
	if isinstance(image_or_path, Image.Image):
		image = image_or_path
	else:
		with Image.open(image_or_path) as opened:
			image = opened.convert('RGB')
			image = image.resize(IMAGE_SIZE)
			image_array = np.asarray(image, dtype=np.float32)
			processed = tf.keras.applications.efficientnet_v2.preprocess_input(image_array)
			processed = np.expand_dims(processed.astype(np.float32), axis=0)
			if logger_obj is not None:
				logger_obj.info(
					'Preprocessed input path=%s shape=%s dtype=%s min=%.6f max=%.6f mean=%.6f',
					str(image_or_path), processed.shape, processed.dtype, float(processed.min()), float(processed.max()), float(processed.mean()),
				)
			return processed

	image = image.convert('RGB').resize(IMAGE_SIZE)
	image_array = np.asarray(image, dtype=np.float32)
	processed = tf.keras.applications.efficientnet_v2.preprocess_input(image_array)
	processed = np.expand_dims(processed.astype(np.float32), axis=0)
	if logger_obj is not None:
		logger_obj.info(
			'Preprocessed input shape=%s dtype=%s min=%.6f max=%.6f mean=%.6f',
			processed.shape, processed.dtype, float(processed.min()), float(processed.max()), float(processed.mean()),
		)
	return processed


def preprocess_image(image_path):
	"""Backward-compatible wrapper for existing callers."""
	return preprocess_for_model(image_path)