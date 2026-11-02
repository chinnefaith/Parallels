import json
import logging
from pathlib import Path

import numpy as np
from django.conf import settings

from .model_loader import get_interpreter
from .preprocessing import preprocess_for_model


logger = logging.getLogger(__name__)
LABELS_PATH = Path(settings.BASE_DIR) / 'seaweed_parallel' / 'model' / 'labels.json'


def load_labels():
	with LABELS_PATH.open(encoding='utf-8') as labels_file:
		labels = json.load(labels_file)
	if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
		raise ValueError('labels.json must contain a list of strings')
	return labels


def _apply_softmax(values):
	values = np.asarray(values, dtype=np.float32)
	values = values - np.max(values)
	exp_values = np.exp(values)
	return exp_values / np.sum(exp_values)


def classify_image(image_path):
	labels = load_labels()
	interpreter = get_interpreter()
	input_details = interpreter.get_input_details()[0]
	output_details = interpreter.get_output_details()[0]
	input_tensor = preprocess_for_model(image_path, logger_obj=logger)
	if input_details['dtype'] != np.float32:
		input_tensor = input_tensor.astype(np.float32)
	interpreter.set_tensor(input_details['index'], input_tensor)
	interpreter.invoke()
	output = interpreter.get_tensor(output_details['index'])
	probabilities = output[0].astype(np.float32)
	if probabilities.shape[0] != len(labels):
		raise ValueError('Model output count does not match labels.json')
	if not np.allclose(np.sum(probabilities), 1.0, atol=1e-4):
		probabilities = _apply_softmax(probabilities)
	predicted_index = int(np.argmax(probabilities))
	confidence = float(probabilities[predicted_index])
	predicted_class = labels[predicted_index]
	logger.info(
		'Prediction image=%s model=%s labels=%s probabilities=%s predicted_index=%s predicted_class=%s confidence=%.6f',
		str(image_path),
		get_interpreter.__module__,
		labels,
		probabilities.tolist(),
		predicted_index,
		predicted_class,
		confidence,
	)
	return {
		'predicted_class': predicted_class,
		'confidence': confidence,
		'class_index': predicted_index,
		'probabilities': probabilities.tolist(),
	}