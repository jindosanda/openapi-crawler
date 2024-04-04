from model import Model

class Commit( Model ):
	table = 'commits'
	id = None
	sha = None
	valid  = None
	commit_date  = None
	api_spec_id = None
	processed_at = None
	file_present = None
	unique_fields = ['api_spec_id', 'sha']

	def __init__(self):
		super().__init__()