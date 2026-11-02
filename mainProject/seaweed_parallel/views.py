import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import MultiImageUploadForm, UserSignupForm
from .models import BenchmarkRun, ClassificationBatch, ClassificationResult
from .processing.events import publish_batch_progress
from .processing.tasks import classify_image


def _prepare_batches(user, limit=None, queryset=None):
	if queryset is None:
		queryset = ClassificationBatch.objects.filter(user=user).prefetch_related('results')
	if limit is not None:
		queryset = queryset[:limit]
	batches = list(queryset)
	for batch in batches:
		batch_results = list(batch.results.all())
		statuses = [result.status for result in batch_results]
		batch.queued_count = statuses.count(ClassificationResult.Status.QUEUED)
		batch.processing_count = statuses.count(ClassificationResult.Status.PROCESSING)
		batch.completed_count = statuses.count(ClassificationResult.Status.COMPLETED)
		batch.failed_count = statuses.count(ClassificationResult.Status.FAILED)
		batch.finished_count = batch.completed_count + batch.failed_count
		batch.progress_percent = round(
			batch.finished_count / batch.total_images * 100
		) if batch.total_images else 0
		confidences = [
			result.confidence for result in batch_results
			if result.confidence is not None
		]
		batch.average_confidence = (
			sum(confidences) / len(confidences) if confidences else None
		)
	return batches


@login_required
def dashboard(request):
	form = MultiImageUploadForm(request.POST or None, request.FILES or None)
	if request.method == 'POST' and form.is_valid():
		images = form.cleaned_data['images']
		batch = ClassificationBatch.objects.create(
			user=request.user,
			total_images=len(images),
		)
		results = []
		for image in images:
			results.append(ClassificationResult.objects.create(
				batch=batch,
				image=image,
			))

		for result in results:
			classify_image.delay(result.pk)
		publish_batch_progress(batch.pk)

		messages.success(
			request,
			f'{len(results)} image task(s) queued for classification.',
		)
		return redirect('/dashboard/#classification-results')

	batches = _prepare_batches(request.user, limit=1)

	all_results = ClassificationResult.objects.filter(
		batch__user=request.user,
	)
	status_counts = {
		status: all_results.filter(status=status).count()
		for status in ClassificationResult.Status.values
	}
	node_rows = all_results.exclude(node_name='').values(
		'node_name', 'worker_name', 'status',
	)
	nodes = {}
	for row in node_rows:
		node = nodes.setdefault(row['node_name'], {
			'name': row['node_name'],
			'workers': set(),
			'tasks': 0,
			'processing': 0,
			'completed': 0,
			'failed': 0,
		})
		if row['worker_name']:
			node['workers'].add(row['worker_name'])
		node['tasks'] += 1
		if row['status'] == ClassificationResult.Status.PROCESSING:
			node['processing'] += 1
		elif row['status'] == ClassificationResult.Status.COMPLETED:
			node['completed'] += 1
		elif row['status'] == ClassificationResult.Status.FAILED:
			node['failed'] += 1
	for node in nodes.values():
		node['workers'] = sorted(node['workers'])
		node['state'] = 'PROCESSING' if node['processing'] else 'OBSERVED'

	return render(request, 'seaweed_parallel/dashboard.html', {
		'form': form,
		'batches': batches,
		'overview': {
			'total': sum(status_counts.values()),
			'queued': status_counts[ClassificationResult.Status.QUEUED],
			'processing': status_counts[ClassificationResult.Status.PROCESSING],
			'completed': status_counts[ClassificationResult.Status.COMPLETED],
			'failed': status_counts[ClassificationResult.Status.FAILED],
		},
		'nodes': sorted(nodes.values(), key=lambda node: node['name']),
	})


@login_required
def history(request):
	paginator = Paginator(
		ClassificationBatch.objects.filter(user=request.user)
		.order_by('-created_at', '-pk')
		.prefetch_related('results'),
		10,
	)
	page_obj = paginator.get_page(request.GET.get('page'))
	return render(request, 'seaweed_parallel/history.html', {
		'batches': _prepare_batches(
			request.user,
			queryset=page_obj.object_list,
		),
		'page_obj': page_obj,
	})


def _load_shell_records():
	detail_section_names = {
		'basic_identification': 'Identification',
		'appearance': 'Appearance',
		'edibility_and_safety': 'Edibility and safety',
	}
	data_path = (
		Path(__file__).resolve().parent.parent
		/ 'static'
		/ 'shell-categories'
		/ 'shell.json'
	)
	with data_path.open(encoding='utf-8') as shell_file:
		shell_records = json.load(shell_file)

	for shell_id, record in enumerate(shell_records):
		identification = record['basic_identification']
		identification['classification'] = identification['classification'].strip()
		record['id'] = shell_id
		image_path = record['image_path'].removeprefix('static/')
		record['image_url'] = (
			static(image_path) if finders.find(image_path) else None
		)
		record['detail_sections'] = [
			{
				'title': title,
				'fields': [
					{
						'label': label.replace('_', ' ').capitalize(),
						'value': value,
					}
					for label, value in record[key].items()
				],
			}
			for key, title in detail_section_names.items()
			if key in record
		]
		record['habitat_fields'] = [
			{
				'label': label.replace('_', ' ').capitalize(),
				'value': value,
			}
			for label, value in record.get('habitat', {}).items()
		]

	return shell_records


@login_required
def shells_library(request):
	category_details = {
		'bivalve': {
			'name': 'Bivalves',
			'image': 'shell-categories/Bivalves.png',
		},
		'gastropod': {
			'name': 'Gastropods',
			'image': 'shell-categories/gastropods.png',
		},
		'polyplacophora': {
			'name': 'Chitons',
			'image': 'shell-categories/Polyplacophora.png',
		},
	}
	categories = {
		slug: {
			'slug': slug,
			'name': details['name'],
			'image_url': (
				static(details['image'])
				if details['image'] and finders.find(details['image'])
				else None
			),
			'shells': [],
		}
		for slug, details in category_details.items()
	}
	shell_records = _load_shell_records()

	for record in shell_records:
		identification = record['basic_identification']
		classification = identification['classification']
		slug = classification.casefold()
		if slug in {'cephalopod', 'scaphopod'}:
			continue
		if slug not in categories:
			categories[slug] = {
				'slug': slug,
				'name': classification,
				'image_url': None,
				'shells': [],
			}

		categories[slug]['shells'].append(record)

	library_categories = [
		category for category in categories.values()
		if category['shells']
	]
	return render(request, 'seaweed_parallel/shells_library.html', {
		'categories': library_categories,
		'shell_count': sum(
			len(category['shells']) for category in library_categories
		),
	})


@login_required
def shell_quiz(request):
	return render(request, 'seaweed_parallel/shell_quiz.html')


@login_required
def shell_detail(request, shell_id):
	shell_records = _load_shell_records()
	if shell_id < 0 or shell_id >= len(shell_records):
		raise Http404('Shell not found.')

	shell = shell_records[shell_id]
	classification = shell['basic_identification']['classification']
	if classification.casefold() in {'cephalopod', 'scaphopod'}:
		raise Http404('Shell not found.')

	related_shells = [
		record for record in shell_records
		if record['id'] != shell_id
		and record['basic_identification']['classification'] == classification
		and record['basic_identification']['classification'].casefold()
		not in {'cephalopod', 'scaphopod'}
	][:4]
	return render(request, 'seaweed_parallel/shell_detail.html', {
		'shell': shell,
		'category_name': classification,
		'similar_species': shell.get('similar_species', []),
		'related_shells': related_shells,
	})


@login_required
def about_us(request):
	return render(request, 'seaweed_parallel/about_us.html')


@login_required
def benchmark_results(request):
	runs = list(
		BenchmarkRun.objects.filter(user=request.user)
		.prefetch_related('measurements')[:20]
	)
	measurements = [
		measurement
		for run in runs
		for measurement in run.measurements.all()
	]
	max_total_time = max(
		(measurement.total_processing_time for measurement in measurements),
		default=0,
	)
	max_speedup = max(
		(measurement.speedup for measurement in measurements),
		default=0,
	)
	for measurement in measurements:
		measurement.total_time_percent = (
			measurement.total_processing_time / max_total_time * 100
			if max_total_time else 0
		)
		measurement.speedup_percent = (
			measurement.speedup / max_speedup * 100
			if max_speedup else 0
		)

	return render(request, 'seaweed_parallel/benchmark.html', {
		'runs': runs,
		'measurements': measurements,
	})


def signin(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	if request.method == 'POST':
		username = request.POST.get('username', '').strip()
		password = request.POST.get('password', '')
		user = authenticate(request, username=username, password=password)

		if user is not None:
			login(request, user)
			next_url = request.GET.get('next')
			if next_url and url_has_allowed_host_and_scheme(
				next_url,
				allowed_hosts={request.get_host()},
				require_https=request.is_secure(),
			):
				return redirect(next_url)
			return redirect('dashboard')

		messages.error(request, 'Invalid username or password.')

	return render(request, 'seaweed_parallel/signin.html')


def signup(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = UserSignupForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		form.save()
		return redirect('signin')

	return render(request, 'seaweed_parallel/signup.html', {'form': form})


@login_required
def signout(request):
	if request.method == 'POST':
		logout(request)
		return redirect('signin')

	return redirect('dashboard')
