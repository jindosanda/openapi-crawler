from datetime import datetime

def log(text, end=None, timestamp=True):
	print( ( datetime.now().strftime("%d/%m/%Y %H:%M:%S") if timestamp else '') +"  "+str(text), end=end)
		