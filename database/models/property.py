from model import Model

class Property( Model ):
	table = 'properties'
	id = None
	api_spec_id = None
	commit_id = None
	component_id  = None
	name = None
	value = None
	valid = None
	unique_fields = ['api_spec_id','commit_id','component_id', 'name']

	def __init__(self):
		super().__init__()
