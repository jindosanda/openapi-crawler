from model import Model
from mysql_lib import mysql_connect

class Counter( Model ):
	table = 'counters'
	id = None
	name = None
	counter  = None
	unique_fields = ['name']

	def __init__(self):
		super().__init__()

	def increment(self):
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		update = f"""UPDATE {self.table} SET counter=counter+1 WHERE name='{self.name}'"""
		cursor.execute ( update )
		connection.commit()
		cursor.close()
		connection.close()
	
	def get(self):
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		select = f"""SELECT counter FROM {self.table} WHERE name='{self.name}'"""
		cursor.execute ( select )
		select_result = cursor.fetchone()
		cursor.close()
		connection.close()
		if select_result[0]:
			return select_result[0]
		else: return None