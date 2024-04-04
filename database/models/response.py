from model import Model

class Response( Model ):
	table = 'responses'
	id = None
	code  = None
	content_type  = None
	components_id  = None
	methods_id  = None
	deprecated = None
	deprecated_in_description = None
	deprecated_components = None
	deprecated_in_description_components = None 
	description = None
	response_schema = None

	unique_fields = ['code', 'method_id']

	def __init__(self):
		super().__init__()