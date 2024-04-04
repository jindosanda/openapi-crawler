from model import Model
import time

class Lock( Model ):
	table = 'locks'
	id = None
	name = None
	locked  = None
	unique_fields = ['lock']

	def __init__(self, lockname):
		super().__init__()
		self.name = lockname

	def acquire( self ):
		if( self.name == None ): 
			raise lockUndefined
		while(True):
			self.get()
			if ( self.locked == True ): 
				time.sleep(1)
				del self.locked
				del self.id
			else:
				self.locked = True
				self.save()
				break
		return True

	def release( self ):
		if( self.name == None ): 
			raise lockUndefined
		self.get()
		self.locked = False
		self.save()