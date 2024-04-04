from model import Model

class SecuritySchema( Model ):
	table = 'security_schemas'
	id = None
	api_spec_id  = None
	commit_id  = None
	name  = None
	value = None
	unique_fields = ['api_spec_id', 'commit_id', 'name']

	def __init__(self):
		super().__init__()