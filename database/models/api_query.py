from model import Model

class ApiQuery( Model ):
	table = 'api_queries'
	id = None
	github_query_id = None
	api_spec_id  = None
	created_at = None
	updated_at = None
	unique_fields = ['github_query_id', 'api_spec_id']

	def __init__(self):
		super().__init__()