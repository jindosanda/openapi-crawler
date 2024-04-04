from model import Model

class Log( Model ):
	table = 'logs'
	id = None
	process = None
	msg  = None
	logdate  = None
	commit_id = None
	errorType = None
	
	def __init__(self):
		super().__init__()