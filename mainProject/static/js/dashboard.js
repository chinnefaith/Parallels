const form = document.getElementById('upload-form');
const zone = document.getElementById('upload-zone');
const input = document.getElementById('id_images');
const previewList = document.getElementById('preview-list');
const count = document.getElementById('selection-count');
const submitButton = document.getElementById('submit-button');
let selectedFiles = [];

function scrollToClassificationResults() {
  const results = document.getElementById('classification-results');
  if (results) results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function syncInput() {
  const transfer = new DataTransfer();
  selectedFiles.forEach((file) => transfer.items.add(file));
  input.files = transfer.files;
}

function renderPreviews() {
  previewList.replaceChildren();
  count.textContent = selectedFiles.length ? `${selectedFiles.length} image(s) ready` : 'No images selected.';
  submitButton.disabled = selectedFiles.length === 0;

  selectedFiles.forEach((file, index) => {
    const card = document.createElement('article');
    card.className = 'preview';
    const image = document.createElement('img');
    image.src = URL.createObjectURL(file);
    image.alt = file.name;
    const label = document.createElement('small');
    label.textContent = file.name;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.addEventListener('click', () => {
      selectedFiles.splice(index, 1);
      syncInput();
      renderPreviews();
    });
    card.append(image, label, remove);
    previewList.append(card);
  });
}

function addFiles(files) {
  selectedFiles = [...selectedFiles, ...Array.from(files)].filter(
    (file, index, all) => index === all.findIndex(
      (item) => item.name === file.name && item.size === file.size,
    ),
  );
  syncInput();
  renderPreviews();
}

form.addEventListener('submit', () => {
  window.setTimeout(scrollToClassificationResults, 0);
});

function setText(parent, field, value) {
  const element = parent.querySelector(`[data-field="${field}"]`);
  if (element) element.textContent = value;
}

function updateBatch(batch, event) {
  setText(batch, 'batch-status', event.batch_status);
  const finished = Number(event.completed) + Number(event.failed);
  const progress = event.total ? Math.round((finished / event.total) * 100) : 0;
  setText(batch, 'progress', `${progress}%`);
  const bar = batch.querySelector('[data-field="progress-bar"]');
  if (bar) bar.style.width = `${progress}%`;
  if (!event.result_id) return;

  const row = batch.querySelector(`[data-result-id="${event.result_id}"]`);
  if (!row) return;
  const confidence = event.confidence === null
    ? null
    : Math.max(0, Math.min(100, Number(event.confidence) * 100));
  setText(row, 'result-status', event.result_status || '-');
  setText(row, 'prediction', event.prediction || '-');
  setText(row, 'confidence', confidence === null ? '-' : `${confidence.toFixed(1)}%`);
  setText(row, 'processing-time', event.processing_time === null ? '-' : `${Number(event.processing_time).toFixed(3)}s`);
  setText(row, 'worker', event.worker || '-');
  setText(row, 'node', event.node || '-');

  const confidenceBar = row.querySelector('[data-field="confidence-bar"]');
  if (confidenceBar) confidenceBar.style.width = `${confidence || 0}%`;
  const review = row.querySelector('[data-field="confidence-state"]');
  if (review) {
    review.textContent = event.result_status === 'COMPLETED' && Number(event.confidence) < .7 ? 'Needs review' : '';
    review.className = review.textContent ? 'needs-review' : '';
  }
}

input.addEventListener('change', () => addFiles(input.files));
['dragenter', 'dragover'].forEach((eventName) => zone.addEventListener(eventName, (event) => {
  event.preventDefault();
  zone.classList.add('is-dragging');
}));
['dragleave', 'drop'].forEach((eventName) => zone.addEventListener(eventName, (event) => {
  event.preventDefault();
  zone.classList.remove('is-dragging');
}));
zone.addEventListener('drop', (event) => addFiles(event.dataTransfer.files));

document.querySelectorAll('[data-batch-id]').forEach((batch) => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  let reconnectTimer;
  function connect() {
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/classification/${batch.dataset.batchId}/`);
    socket.onmessage = (message) => updateBatch(batch, JSON.parse(message.data));
    socket.onclose = () => {
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 1500);
    };
  }
  connect();
});

document.querySelectorAll('.result-image').forEach((cell) => {
  const imagePath = cell.textContent.trim();
  if (!imagePath || imagePath === '-') return;
  cell.textContent = '';
  const image = document.createElement('img');
  image.className = 'result-thumbnail';
  image.src = `/media/${imagePath}`;
  image.alt = imagePath;
  cell.append(image);
});

document.querySelectorAll('[data-field="confidence"]').forEach((element) => {
  const value = Number(element.textContent.trim());
  if (!Number.isNaN(value)) element.textContent = `${(value * 100).toFixed(1)}%`;
});
document.querySelectorAll('[data-field="average-confidence"]').forEach((element) => {
  const value = Number(element.textContent.trim());
  if (!Number.isNaN(value)) element.textContent = `${(value * 100).toFixed(1)}%`;
});
document.querySelectorAll('[data-field="confidence-bar"]').forEach((element) => {
  const value = Number(element.style.width.replace('%', ''));
  if (value <= 1) element.style.width = `${value * 100}%`;
});
document.querySelectorAll('[data-field="worker"], .worker-chip').forEach((element) => {
  element.textContent = element.textContent.trim().split('@', 1)[0] || '-';
});

if (window.location.hash === '#classification-results') {
  window.setTimeout(scrollToClassificationResults, 100);
}
