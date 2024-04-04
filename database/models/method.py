from model import Model

class Method( Model ):
	table = 'methods'
	id = None
	name  = None
	type  = None
	request_body  = None
	api_spec_id  = None
	commit_id  = None
	deprecated = 0
	deprecated_in_description = 0
	unique_fields = ['name', 'type', 'api_spec_id', 'commit_id']

	def __init__(self):
		super().__init__()