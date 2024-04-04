from model import Model

class UrlToCheck( Model ):
	table = 'urls_to_check'
	id = None
	repo_name = None
	owner  = None
	filepath  = None
	filename = None
	url = None
	github_query_id = None
	created_at = None
	updated_at = None
	unique_fields = ['owner', 'repo_name', 'filepath', 'url', 'github_query_id']

	def __init__(self):
		super().__init__()