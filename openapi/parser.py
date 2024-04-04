import sys, os
sys.path.append('./database/')
sys.path.append('./database/models/')
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
from prance import ResolvingParser, BaseParser, ValidationError
from prance.util.url import ResolutionError
from prance.util.resolver import RESOLVE_HTTP, RESOLVE_FILES
from prance.util.iterators import item_iterator
from openapi_spec_validator import validate_spec
from mysql_lib import mysql_connect
import mysql.connector
import ntpath
import requests
from pipeline import Pipeline
import utils
from method import Method
from parameter import Parameter
from response import Response
from commit import Commit
from component import Component
from security_schema import SecuritySchema
from property import Property
from counter import Counter
from log import Log
import time
from datetime import datetime
import pymysql
import multiprocessing as mp
import json
import signal
from contextlib import contextmanager

class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

parser_counter = 0

def saveSecuritySchema( api_spec_id, commit_id, data ):
	try:
		for security_schema in data:
			securitySchema = SecuritySchema()
			securitySchema.api_spec_id = api_spec_id
			securitySchema.commit_id = commit_id
			#limit the length of the security schema name to 255 characters
			securitySchema.name = security_schema[:255]
			securitySchema.value = json.dumps( data[security_schema] )
			if( securitySchema.name != None ):
				securitySchema.save()
	except Exception as e:
		print( e )

class Parser( Pipeline ):

	methods = ['get', 'post', 'patch', 'delete', 'put', 'head', 'options']
	
	def __init__(self):
		super().__init__()

	def getData( self, api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id ):
		if len(os.path.dirname(filepath)) == 0:
			commit_filepath = f"commits/{commit}/{filename}"
		else:
			commit_filepath = f"commits/{commit}/{os.path.dirname(filepath)}/{filename}"

		oas_file = self.filePath(owner, repo_name, commit_filepath, filename) 
		if '-v'	in sys.argv:
			utils.log(f"Parsing {oas_file}")
		
		commit = Commit()
		commit.id = commit_id
		commit.processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		
		try:
			with time_limit(10):
				parser = ResolvingParser( oas_file, 
					backend = 'openapi-spec-validator',
					strict=False )	
		except Exception as deep_e:
			print( "1st exception: "+str(deep_e) )
			try:
				with time_limit(10):
					parser = BaseParser( oas_file, 
						backend = 'openapi-spec-validator',
						strict=False )
			except Exception as e2:
				print( "2nd exception: "+str(e2) )
				utils.log("Validation exception detected")
				# log = Log()
				# log.process='parser'
				# log.commit_id = commit_id
				# log.errorType = type(e2).__name__
				# log.msg = pymysql.escape_string( str(e2) )
				# log.save()
				commit.valid = 0
				commit.save()
				return
		
		commit.api_version, commit.api_title = parser.specification['info']['version'], parser.specification['info']['title']
		if( 'openapi' in parser.specification ):
			commit.oas_version = parser.specification['openapi']
		elif( 'swagger' in parser.specification ):
			commit.oas_version = parser.specification['swagger']

		if 'paths' in parser.specification:
			for path in parser.specification['paths']:
				try:
					for method_type in parser.specification['paths'][path]:
						if method_type in self.methods:
							method = Method()
							method.api_spec_id = api_spec_id
							method.commit_id = commit_id
							#limit the length of the method name to 255 characters
							method.name = path[:255]
							method.type = method_type
							if "deprecated" in parser.specification['paths'][path][method_type]:
								if( parser.specification['paths'][path][method_type]['deprecated'] == True):
									method.deprecated = 1
							if "description" in parser.specification['paths'][path][method_type]:
								if( "deprecated" in parser.specification['paths'][path][method_type]['description']):
									method.deprecated_in_description = 1
							method.save()

							if "parameters" in parser.specification['paths'][path][method_type]:
								for parameter in parser.specification['paths'][path][method_type]['parameters']:
									param = Parameter()
									param.method_id = method.id
									if 'name' in parameter:
										# limit the length of the parameter name to 255 characters
										param.name = parameter['name'][:255]
									if 'schema' in parameter:
										if 'type' in parameter['schema']:
											param.type = parameter['schema']['type']
										if 'default' in parameter['schema']:
											param.default_value = parameter['schema']['default']
										if 'enum' in parameter['schema']:
											# convert into json
											param.enum = json.dumps( parameter['schema']['enum'] )
									if 'required' in parameter:
										param.required = parameter['required']
									if 'in' in parameter:
										param.location_in = parameter['in']
									if 'description' in parameter:
										param.description = parameter['description']
									if 'schema' in parameter:
										param.parameter_schema = json.dumps( parameter['schema'] )
									if( param.name != None):
										param.save()
							if "responses" in parser.specification['paths'][path][method_type]:
								for response_code in parser.specification['paths'][path][method_type]["responses"]:
									response = Response()
									response.method_id = method.id
									response.code = response_code
									if 'description' in parser.specification['paths'][path][method_type]["responses"][response_code]:
										response.description = parser.specification['paths'][path][method_type]["responses"][response_code]['description']
									if "content" in parser.specification['paths'][path][method_type]["responses"][response_code]:
										try:
											response_type = list(parser.specification['paths'][path][method_type]["responses"][response_code]['content'].keys())[0]
											response.content_type = response_type
											if 'schema' in parser.specification['paths'][path][method_type]["responses"][response_code]['content'][response_type]:
												response.response_schema = json.dumps( parser.specification['paths'][path][method_type]["responses"][response_code]['content'][response_type]['schema'] )
											
										except IndexError:
											response_type = None
									response.save()
				except Exception as e:
					print( e )

		# OpenAPI v3
		if 'components' in parser.specification:
			if 'schemas' in parser.specification['components']:
				for schema in parser.specification['components']['schemas']:
					if schema != None:
						component = Component()
						component.api_spec_id = api_spec_id
						component.commit_id = commit_id
						# limit the length of the component name to 255 characters
						component.name = schema[:255]
						component.save()
						if 'properties' in parser.specification['components']['schemas'][schema]:
							properties = parser.specification['components']['schemas'][schema]['properties']
							for prop_name in properties:
								try:
									value = json.dumps( properties[prop_name] )
								except:
									value = ''
								if prop_name in ('type', 'allOf', 'oneOf', 'anyOf', 'not', 'items', 'properties', 'additionalProperties', 'description', 'format'):
									valid = True
								else:
									valid = False

								try:
									property_entry = Property()
									property_entry.api_spec_id = api_spec_id
									property_entry.commit_id = commit_id
									property_entry.component_id = component.id
									# limit the length of the property name to 255 characters
									property_entry.name = prop_name[:255]
									property_entry.value = value
									property_entry.valid_v3 = valid
									if( property_entry.name != None ):
										property_entry.save()
								except Exception as e:
									print( e )
									print( property_entry.value )
			if 'securitySchemes' in parser.specification['components']:
				saveSecuritySchema( api_spec_id, commit_id, parser.specification['components']['securitySchemes'] )

		#Swagger 2.0
		if 'securityDefinitions' in parser.specification:
			saveSecuritySchema( api_spec_id, commit_id, parser.specification['securityDefinitions'] )

		#Swagger 2.0
		if 'definitions' in parser.specification:
			for definition in parser.specification['definitions']:
				component = Component()
				component.api_spec_id = api_spec_id
				component.commit_id = commit_id
				# limit the length of the component name to 255 characters
				component.name = definition[:255]
				component.save()
				for prop in parser.specification['definitions'][definition]:
					try:
						value = json.dumps( parser.specification['definitions'][definition][prop] )
					except:
						value = ''
					try:
						property_entry = Property()
						property_entry.api_spec_id = api_spec_id
						property_entry.commit_id = commit_id
						property_entry.component_id = component.id
						# limit the length of the property name to 255 characters
						property_entry.name = prop[:255]
						property_entry.value = value
						property_entry.valid_v3 = False
						if( property_entry.name != None ):
							property_entry.save()
					except Exception as e:
						print( e )
						print( property_entry.value )
		commit.save()

	def getFiles( self, limit=None ):
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		where = f"WHERE api.id = c.api_spec_id AND c.processed_at IS NULL AND c.valid = true"
		mysql_select = f"""SELECT api.id, api.repo_name, api.owner, api.filepath, api.filename, api.updated_at, c.sha, c.id as commit_id 
			FROM api_specs as api, commits as c"""
		# start = None
		# end = None
		# if( len(sys.argv) > 1 ):
		# 	for arg in sys.argv:
		# 		if( 'from=' in arg ):
		# 			start = arg[5:]
		# 		elif( 'to=' in arg ):
		# 			end = arg[3:]
		# 		elif( 'api=' in arg ):
		# 			api = arg[4:]
		# 			where += f" and api.id={api}"
		# 	if( start is not None and end is not None):
		# 		limit = f"LIMIT {start},{end}"
		if limit is not None:
			limit_str = f"LIMIT {limit}"
		mysql_select = f"{mysql_select} {where} {limit_str}"
		
		cursor.execute(mysql_select)
		mysql_result = cursor.fetchall()
		cursor.close()
		connection.close()
		return mysql_result

def processRecord( record ):
	api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id = record
	parser = Parser()
	parser.getData( api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id )
	counter = Counter()
	counter.name = 'parser'
	counter.increment()

if __name__ == "__main__":
	parser = Parser()
	counter = Counter()
	counter.name = 'parser'
	counter.counter = 0
	counter.save()
	

	while True:
		records = parser.getFiles(limit=1000)
		tot_records = len(records)
		print( f"Found {tot_records} records to parse")
		if tot_records == 0:
			counter.counter = 0
			counter.save()
			# wait 10 minutees before starting again
			print(f"Waiting 10 minutes before starting again")
			time.sleep(60*10)
			continue

		if '--single' in sys.argv:
			for record in records:
				processRecord( record )
			break
		else:
			num_processes = int(os.getenv('PARALLEL_CPU_USAGE'))
			with mp.Pool(num_processes) as pool:
				pool.map(processRecord, records)
			
			# pool = mp.Pool(num_processes)
			# pool.map(processRecord, records)

			# Attendere la terminazione di tutti i processi
			# pool.close()
			# pool.join()

			print("All processes have finished.")
			# print(f"Waiting 10 minutes before starting again")
			# time.sleep(60*10)

			