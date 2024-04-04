from mysql_lib import mysql_connect
import json 
from sqlescapy import sqlescape
import sys 

class Model():
	def __init__(self):
		pass

	def __str__( self ):
		return json.dumps(vars(self))

	def insert(self):
		# if hasattr(self, 'unique_fields'):
		# 	unique_fields_filled = True
		# 	where = ''
		# 	if( len(self.unique_fields) == 0 ): unique_fields_filled = False
		# 	for k in self.unique_fields:
		# 		if( getattr(self,k) == None ): 
		# 			unique_fields_filled = False
		# 			break
		# 		if ( type(getattr(self,k)) == str ):
		# 			attribute = "'"+sqlescape(getattr(self,k))+"'"
		# 		elif( 'datetime' in str( getattr(self,k) ) ):
		# 			attribute = "'"+getattr(self,k)+"'"
		# 		else:
		# 			attribute = getattr(self,k)
		# 		where += f"{k}="+( f"{attribute}" )+" AND "

		# 	if unique_fields_filled == True:
		# 		where = where[:-5]
		# 		select = f"""SELECT id as c FROM {self.table} WHERE({where}) LIMIT 1"""
		# 		connection = mysql_connect()
		# 		cursor = connection.cursor(buffered=True)
		# 		cursor.execute ( select )
		# 		records = cursor.fetchall()
		# 		if cursor.rowcount > 0:
		# 			# if(hasattr(self, 'api_spec_id') and self.api_spec_id == 51 and hasattr(self, 'commit_id') and self.commit_id == 65): 
		# 			# 	print( select )
		# 			self.id = records[0][0]
		# 			cursor.close()
		# 			connection.close()
		# 			self.update()
		# 			return

		# values, fields = '', ''
		# for k,v in vars(self).items():
		# 	fields += f"{k},"
		# 	if( type(v) == str ): 
		# 		attribute = sqlescape(v)
		# 		values += f"\'{attribute}\',"
		# 	elif v is None:
		# 		values += f"NULL,"
		# 	elif( 'datetime' in str( type(v) ) ):
		# 		values += f"'{v}',"
		# 	else:
		# 		values += f"{v},"
		# values = values[:-1]
		# fields = fields[:-1]
		# insert = f"""INSERT INTO {self.table}({fields}) VALUES({values})"""
		# # if(hasattr(self, 'api_spec_id') and self.api_spec_id == 51 and hasattr(self, 'commit_id') and self.commit_id == 65): 
		# # print( insert )
		# connection = mysql_connect()
		# cursor = connection.cursor(buffered=True)
		# cursor.execute(insert)
		# self.id = cursor.lastrowid
		# connection.commit()
		# cursor.close()
		# connection.close()
		if hasattr(self, 'unique_fields'):
			unique_fields_filled = all(getattr(self, field) is not None for field in self.unique_fields)
			where_conditions = []
			params = []

			if unique_fields_filled:
				for k in self.unique_fields:
					where_conditions.append(f"{k} = %s")
					params.append(getattr(self, k))
				
				where_clause = " AND ".join(where_conditions)
				select_query = f"SELECT id FROM {self.table} WHERE {where_clause} LIMIT 1"
				connection = mysql_connect()
				cursor = connection.cursor(buffered=True)
				cursor.execute(select_query, params)
				records = cursor.fetchall()

				if cursor.rowcount > 0:
					self.id = records[0][0]
					cursor.close()
					connection.close()
					self.update()
					return

		fields, values = zip(*[(k, v) for k, v in vars(self).items()])
		placeholders = ["%s"] * len(values)
		insert_query = f"INSERT INTO {self.table} ({','.join(fields)}) VALUES ({','.join(placeholders)})"

		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		cursor.execute(insert_query, values)
		self.id = cursor.lastrowid
		connection.commit()
		cursor.close()
		connection.close()

	def update( self ):
		# stmt = ''
		# for k,v in vars(self).items():
		# 	# if( v is None ):
		# 	# 	print("ERROR: None detected ", vars(self).items())
		# 	if( k == 'id'): continue
		# 	if( type(v) == str ): 
		# 		attribute = sqlescape(v)
		# 		stmt += f"{k}=\'{attribute}\',"
		# 	elif( 'datetime' in str( type(v) ) ):
		# 		stmt += f"{k}=\'{v}\',"
		# 	else: stmt += f"{k}={v},"
		# stmt = stmt[:-1]
		# update = f"""UPDATE {self.table} SET {stmt} WHERE id={self.id}"""
		# # print( update )
		# # if(hasattr(self, 'api_spec_id') and self.api_spec_id == 51 and hasattr(self, 'commit_id') and self.commit_id == 65): 
		# # print( update )
		# connection = mysql_connect()
		# cursor = connection.cursor(buffered=True)
		# cursor.execute(update)
		# connection.commit()
		# cursor.close()
		# connection.close()
		attributes = []
		params = []

		for k, v in vars(self).items():
			if k == 'id' or v is None:
				continue
			attributes.append(f"{k} = %s")
			params.append(v)

		stmt = ", ".join(attributes)
		params.append(self.id)  # Add 'id' at the end for the WHERE clause
		update_query = f"UPDATE {self.table} SET {stmt} WHERE id = %s"

		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		cursor.execute(update_query, params)
		connection.commit()
		cursor.close()
		connection.close()

	def save( self ):
		if( self.id is None ):
			self.insert()
		else:
			self.update()

	def get( self ):
		stmt = ''
		for k,v in vars(self).items():
			if( type(v) == str ): 
				attribute = sqlescape(v)
				stmt += f"{k}=\'{attribute}\' AND "
			elif( 'datetime' in str( type(v) ) ):
				stmt += f"{k}=\'{v}\' AND "
			else: stmt += f"{k}={v} AND "
		stmt = stmt[:-5]
		select = f"""SELECT * FROM {self.table} WHERE {stmt} LIMIT 1"""
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		cursor.execute(select)
		results = cursor.fetchall()
		select = f"""DESCRIBE {self.table}"""
		cursor.execute(select)
		schema = cursor.fetchall()
		i = 0
		try:
			for value in results[0]:
				fieldName = schema[i][0]
				self.__dict__[fieldName] = value
				i+=1
		except:
			print("results is ")
			print(results)

		connection.commit()
		cursor.close()
		connection.close()
