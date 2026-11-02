import os
def get_worker_name(task_request):
	hostname = task_request.hostname
	if hostname:
		return hostname.split('@', 1)[0]
	return 'worker'


def get_node_name():
	return os.environ.get('SEAWEED_NODE_NAME', 'NODE_LOCAL')