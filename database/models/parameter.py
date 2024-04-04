from model import Model

class Parameter( Model ):
	table = 'parameters'
	id = None
	name  = None
	type  = None
	required  = None
	methods_id  = None
	default_value  = None
	location_in = None
	enum = None
	description = None
	parameter_schema = None
	unique_fields = ['name', 'method_id']

	def __init__(self):
		super().__init__()