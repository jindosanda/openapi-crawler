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
from mysql_lib import mysql_connect
import mysql.connector
from dotenv import load_dotenv
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
import re
import yaml
import traceback

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

class MethodsDeprecated:
	
	methods = ['get', 'post', 'patch', 'delete', 'put', 'head', 'options']

	def __init__( self ):
		load_dotenv()
		self.max_file_size = int(os.getenv('MAX_FILE_SIZE'))
		self.output_folder = os.getenv('OUTPUT_FOLDER')
		self.github_base_url = os.getenv('GITHUB_BASE_URL')

	def getFiles( self ):
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
# 		mysql_select = f"""SELECT api.id, api.repo_name, api.owner, api.filepath, api.filename, api.updated_at, c.sha, c.id as commit_id 
# FROM api_specs as api, commits as c
# WHERE api.id = c.api_spec_id AND api_spec_id in (select m.api_spec_id from methods m
# left join commits c on c.id=m.commit_id
# where valid=1 and deprecated=1 and c.processed_at is null);"""

		mysql_select = """SELECT a.id, a.repo_name, a.owner, a.filepath, a.filename, a.updated_at, c.sha, c.id as commit_id 
FROM api_specs a
left join commits c on c.api_spec_id=a.id
left join methods m on m.commit_id=c.id
where valid=1 and deprecated=1 and c.processed_at is null;"""
		
		cursor.execute(mysql_select)
		mysql_result = cursor.fetchall()
		# print( mysql_result )
		cursor.close()
		connection.close()
		return mysql_result

	def filePath(self, owner, repo, filepath, filename):
		if os.path.isabs( filepath ):
			path = os.path.abspath( filepath+'/'+filename )
		else:	
			relative_path = f"{self.output_folder}{owner}/{repo}/{os.path.dirname(filepath)}/{filename}"
			absolute_path = os.path.abspath( relative_path )
			path = absolute_path
		return path

	def getData( self, api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id ):
		connection = mysql_connect()
		cursor = connection.cursor(buffered=True)
		
		if len(os.path.dirname(filepath)) == 0:
			commit_filepath = f"commits/{commit}/{filename}"
		else:
			commit_filepath = f"commits/{commit}/{os.path.dirname(filepath)}/{filename}"

		oas_file = self.filePath(owner, repo_name, commit_filepath, filename) 
		# utils.log(f"Parsing {oas_file}")
		commit = Commit()
		commit.id = commit_id
		commit.processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

		try:
			with time_limit(10):
				parser = BaseParser( oas_file, 
					backend = 'openapi-spec-validator',
					strict=False )	
		except Exception as deep_e:
			# commit.valid = 0
			commit.save()
			return
		
		# commit.api_version, commit.api_title = parser.specification['info']['version'], parser.specification['info']['title']
		# if( 'openapi' in parser.specification ):
		# 	commit.oas_version = parser.specification['openapi']
		# elif( 'swagger' in parser.specification ):
		# 	commit.oas_version = parser.specification['swagger']

		# OpenAPI v3
		if 'components' in parser.specification:
			if 'schemas' in parser.specification['components']:
				for schema in parser.specification['components']['schemas']:
					if schema != None:
						component = Component()
						component.api_spec_id = api_spec_id
						component.commit_id = commit_id
						component.name = schema
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
									property_entry.name = prop_name
									property_entry.value = value
									# print( value )
									property_entry.valid_v3 = valid
									if( property_entry.name != None ):
										property_entry.save()
								except Exception as e:
									# print( e )
									print( property_entry.value )

		#Swagger 2.0
		if 'definitions' in parser.specification:
			for definition in parser.specification['definitions']:
				component = Component()
				component.api_spec_id = api_spec_id
				component.commit_id = commit_id
				component.name = definition
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
						property_entry.name = prop
						property_entry.value = value
						property_entry.valid_v3 = False
						if( property_entry.name != None ):
							property_entry.save()
					except Exception as e:
						print( e )
						print( property_entry.value )
		
		if 'paths' in parser.specification:
			for path in parser.specification['paths']:
				try:
					for method_type in parser.specification['paths'][path]:
						if method_type in self.methods:
							method = Method()
							method.api_spec_id = api_spec_id
							method.commit_id = commit_id
							method.name = path
							method.type = method_type
							if "deprecated" in parser.specification['paths'][path][method_type]:
								if( parser.specification['paths'][path][method_type]['deprecated'] == True):
									method.deprecated = 1
								else:
									method.deprecated = 0
							if "description" in parser.specification['paths'][path][method_type]:
								if( "deprecat" in parser.specification['paths'][path][method_type]['description']):
									method.deprecated_in_description = 1
							method.save()
							
							# if "parameters" in parser.specification['paths'][path][method_type]:
							# 	# print( parser.specification['paths'][path][method_type]['parameters'] )
							# 	for parameter in parser.specification['paths'][path][method_type]['parameters']:
							# 		param = Parameter()
							# 		param.method_id = method.id
							# 		if 'name' in parameter:
							# 			param.name = parameter['name']
							# 		if 'schema' in parameter and 'type' in parameter['schema']:
							# 			param.type = parameter['schema']['type']
							# 		if 'required' in parameter:
							# 			param.required = parameter['required']
							# 		if 'deprecated' in parameter:
							# 			param.deprecated = parameter['deprecated']
							# 		if 'description' in parameter:
							# 			param.description = parameter['description']
							# 			if( 'deprecat' in parameter['description'] ):
							# 				param.deprecated_in_description = 1
							# 		if( param.name != None):
							# 			param.save()
							if "responses" in parser.specification['paths'][path][method_type]:
								for response_code in parser.specification['paths'][path][method_type]["responses"]:
									response = Response()
									response.api_spec_id = api_spec_id
									response.commit_id = commit_id
									response.method_id = method.id
									response.code = response_code
									if( 'description' in parser.specification['paths'][path][method_type]["responses"][response_code] and "deprecat" in parser.specification['paths'][path][method_type]["responses"][response_code]['description']):
										response.deprecated_in_description = 1
									if "content" in parser.specification['paths'][path][method_type]["responses"][response_code]:
										# if 'schema' in parser.specification['paths'][path][method_type]["responses"][response_code]['content']:
										try:
											response_content = parser.specification['paths'][path][method_type]["responses"][response_code]['content']
											response_type = list(response_content.keys())[0]
											response.content_type = response_type
										except IndexError as e:
											response_type = None
											# print("Exception", e)

										if response_type in response_content and "schema" in response_content[response_type]:
											if( "description" in response_content[response_type]['schema'] and "deprecat" in response_content[response_type]['schema']['description']):
												response.deprecated_in_description_components = 1
											schema_str = str(response_content[response_type]['schema'])
											if('deprecated: true' in schema_str):
												response.deprecated_components = 1
											elif( '$ref' in schema_str ):
												component_name = None
												for s in schema_str.split("'"):
													if( s.startswith('#/components/schemas/')):
														component_name = s[len('#/components/schemas/'):]
														break
												if( component_name is not None ):
													sql_comp = f"""SELECT p.value FROM api_ace_crawler.properties p
left join components c on c.id=p.component_id where p.api_spec_id={api_spec_id} and p.commit_id={commit_id} and c.name='{component_name}' and p.value like '%description:%';"""
													cursor.execute(sql_comp)
													mysql_result = cursor.fetchall()
													for desc in mysql_result:
														try:
															obj = yaml.load(desc[0], yaml.SafeLoader)
															if('deprecated' in obj and obj['deprecated']=='true'):
																response.deprecated_components = 1
																print('FOUND deprecated_components')
															if('description' in obj and 'deprecat' in obj['description']):
																response.deprecated_in_description_components = 1
																print('FOUND deprecated_in_description_components')
															if(response.deprecated_components==1 and response.deprecated_in_description_components==1):
																break
														except:
															pass
# 													# old one
# 													sql_count_dep = f"""SELECT count(*) FROM api_ace_crawler.properties p
# left join components c on c.id=p.component_id where p.api_spec_id={api_spec_id} and p.commit_id={commit_id} and c.name='{component_name}' and p.value like '%deprecated: true%';"""
													
# 													cursor.execute(sql_count_dep)
# 													mysql_result = cursor.fetchall()
# 													# response.deprecated_components = 1 if mysql_result[0][0] > 0 else 0
# 													response.deprecated_components = mysql_result[0][0]
# 													if( response.deprecated_components > 0 ):
# 														print( sql_count_dep )
										



									if "deprecated" in parser.specification['paths'][path][method_type]["responses"][response_code]:
										# print("FOUND deprecated", parser.specification['paths'][path][method_type]["responses"][response_code]['deprecated'], parser.specification['paths'][path][method_type]["responses"][response_code]['deprecated'] == 'true' )
										if( parser.specification['paths'][path][method_type]["responses"][response_code]['deprecated'] == 'true'):
											response.deprecated = 1

									if "description" in parser.specification['paths'][path][method_type]["responses"][response_code]:
										response.description = parser.specification['paths'][path][method_type]["responses"][response_code]['description']
										if "deprecat" in parser.specification['paths'][path][method_type]["responses"][response_code]['description']:
											# print('FOUND deprecated_in_description')
											response.deprecated_in_description = 1


									# print( parser.specification['paths'][path][method_type]["responses"][response_code]['content'] )

									# if 'schema' in parser.specification['paths'][path][method_type]["responses"][response_code]['content'][response_type]:
									# 	print( parser.specification['paths'][path][method_type]["responses"][response_code]['content'] )
										# if 'type' in parser.specification['paths'][path][method_type]["responses"][response_code]['content'][response_type]['schema']:
										# 	if 'items' in parser.specification['paths'][path][method_type]["responses"][response_code]['content'][response_type]['schema']['type']:
										# 		pass

									response.save()
				except Exception as e:
					print( "Exception", e )
					traceback.print_exc()
		commit.save()
		cursor.close()
		connection.close()


def processRecord(api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id):
	md = MethodsDeprecated()
	md.getData( api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id )
	
	
if __name__=="__main__":
	md = MethodsDeprecated()
	i = 0
	pool = mp.Pool(int( os.getenv('PARALLEL_CPU_USAGE' ))) 
	for file in md.getFiles():
		# SELECT api.id, api.repo_name, api.owner, api.filepath, api.filename, api.updated_at, c.sha, c.id as commit_id 
		api_spec_id = file[0]
		repo_name = file[1]
		owner = file[2]
		filepath = file[3]
		filename = file[4]
		updated_at = file[5]
		commit = file[6]
		commit_id = file[7]
		
		pool.apply_async( processRecord, args=(file))
		i+=1		
	pool.close()
	pool.join()

		# md.getData( api_spec_id, repo_name, owner, filepath, filename, updated_at, commit, commit_id )



