from model import Model

class Component( Model ):
	table = 'components'
	id = None
	api_spec_id  = None
	commit_id  = None
	name  = None
	filepath = None
	unique_fields = ['api_spec_id', 'commit_id', 'name']

	def __init__(self):
		super().__init__()