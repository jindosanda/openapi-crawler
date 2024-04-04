import sys, os
sys.path.append('./database/')
sys.path.append('./database/models/')
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
from mysql_lib import mysql_connect
from pipeline import Pipeline
import utils
import requests
from prance import ResolvingParser, BaseParser
import time
from log import Log
import pymysql
from git_utils import downloadFile, is_valid_filename
import multiprocessing as mp
from signal import signal, SIGTERM, SIGINT, SIGPIPE, SIG_DFL
signal(SIGPIPE,SIG_DFL)
import json
import signal
from contextlib import contextmanager
import chardet

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

class Validator( Pipeline ):

	def __init__(self):
		super().__init__()
		self.connection = mysql_connect()
		self.cursor = self.connection.cursor(buffered=True)

	def getJsonReferences(self, obj, key):
		if key in obj and not obj[key].startswith('#') and not obj[key].startswith('http'): 
			if( '#' in obj[key] ):
				ref = obj[key][:obj[key].index('#')]
			else: ref = obj[key]
			self.refs.append( ref )
			return
		for k, v in obj.items():
			if isinstance(v,dict):
				self.getJsonReferences(v, key)
		return

	# def checkReferencies( self, url, owner, repo_name, filepath, filename ):
	# 	oas_file = self.filePath(owner, repo_name, filepath, filename)
	# 	# utils.log(f"Checking references: {owner}/{repo_name} - {filepath}")
		
	# 	try:
	# 		with open(oas_file, "r") as file:
	# 			file_content = file.read()
	# 	except IOError:
	# 		# utils.log('Downloading file: '+oas_file)
	# 		downloadFile( url, owner, repo_name, filepath )
	# 		with open(oas_file, "r") as file:
	# 			file_content = file.read()

	# 	content = file_content.split('\n')
	# 	content = map(lambda a : a.strip(), content)
		
	# 	ext = os.path.basename( oas_file )[-4:]
	# 	if( ext == 'json'):
	# 		print( oas_file )
	# 		oas_dict = json.loads( file_content )
	# 		del file_content
	# 		self.refs = []
	# 		self.getJsonReferences( oas_dict, '$ref' )
	# 		if( len(self.refs) > 0 ):
	# 			file_to_download = self.refs.pop()
	# 			print( not os.path.exists( self.filePath(owner, repo_name, os.path.dirname(oas_file), file_to_download) ) )
	# 			if not os.path.exists( self.filePath(owner, repo_name, os.path.dirname(oas_file), file_to_download) ):
	# 				download = self.downloadReference( url, os.path.dirname(oas_file), file_to_download )
	# 				if download == True: 
	# 					self.checkReferencies( url, owner, repo_name, os.path.dirname(oas_file), file_to_download )		

	# 	else:
	# 		for stmt in list( content ):
	# 			if not stmt.startswith('#'):
	# 				if '$ref' in stmt: 
	# 					stmt = stmt.replace('"', '').replace("'","")
	# 					pos = stmt.find('#')
	# 					if pos > -1: # hash found
	# 						# Internal reference
	# 						if( stmt[6:].startswith('#') ): continue
	# 						# External reference
	# 						else:
	# 							file_to_download = stmt[6:pos]
	# 					elif(' ' in stmt[6:]): #non valid reference
	# 						continue
	# 					else: # external reference
	# 						if(stmt.startswith('http')):
	# 							file_to_download = stmt    
	# 						else:
	# 							file_to_download = stmt[6:]

	# 					if len(file_to_download) == 0: continue

	# 					if file_to_download[-1] == '/': 
	# 						file_to_download = file_to_download[:-1]
						
	# 					# print( ' >> '+ self.filePath(owner, repo_name, os.path.dirname(oas_file), file_to_download))
	# 					if not os.path.exists( self.filePath(owner, repo_name, os.path.dirname(oas_file), file_to_download) ):
							
	# 						download = self.downloadReference( url, os.path.dirname(oas_file), file_to_download )
	# 						if download == True: 
	# 							self.checkReferencies( url, owner, repo_name, os.path.dirname(oas_file), file_to_download )
	# 		del content

	# Versione iterativa di checkreferencies
	def checkReferencies(self, url, owner, repo_name, filepath, filename):
		to_check = [(filepath, filename)]  # Coda di file da controllare

		while to_check:
			current_filepath, current_filename = to_check.pop()
			oas_file = self.filePath(owner, repo_name, current_filepath, current_filename)

			try:
				with open(oas_file, "r", errors='ignore') as file:
					file_content = file.read()
			except UnicodeDecodeError:
				try:
					encoding = chardet.detect(file_content)['encoding']
					with open(oas_file, "r", encoding=encoding) as file:
						file_content = file.read()
				except:
					continue
			except IOError:
				downloadFile(url, owner, repo_name, current_filepath)
				with open(oas_file, "r") as file:
					file_content = file.read()
			
			ext = os.path.basename(oas_file)[-4:]
			if ext == '.json':
				oas_dict = json.loads(file_content)
				self.refs = []
				self.getJsonReferences(oas_dict, '$ref')
				del oas_dict

				for ref in self.refs:
					ref_filepath = os.path.dirname(oas_file)
					ref_filename = ref
					if( ref_filename is not None and ( ref_filename.endswith('.json') or ref_filename.endswith('.yaml') or ref_filename.endswith('.yml') ) ):
						if not os.path.exists(self.filePath(owner, repo_name, ref_filepath, ref_filename)):
							download = self.downloadReference(url, ref_filepath, ref_filename)
							if download:
								to_check.append((ref_filepath, ref_filename))
				del self.refs

			else:
				file_content = map(lambda a: a.strip(), file_content.split('\n'))
				for stmt in list(file_content):
					if not stmt.startswith('#') and '$ref' in stmt:
						stmt = stmt.replace('"', '').replace("'", "")
						pos = stmt.find('#')
						if pos > -1:
							file_to_download = stmt[6:pos] if not stmt[6:].startswith('#') else None
						elif ' ' not in stmt[6:]:
							file_to_download = stmt[6:] if not stmt.startswith('http') else stmt
						else:
							continue

						if file_to_download and file_to_download[-1] == '/':
							file_to_download = file_to_download[:-1]

						# check if file_to_download is a valid filename
						
						if( file_to_download is not None and ( file_to_download.endswith('.json') or file_to_download.endswith('.yaml') or file_to_download.endswith('.yml') ) ):
							if file_to_download and not os.path.exists(self.filePath(owner, repo_name, os.path.dirname(oas_file), file_to_download)):
								download = self.downloadReference(url, os.path.dirname(oas_file), file_to_download)
								if download:
									to_check.append((os.path.dirname(oas_file), file_to_download))
			del file_content

	def downloadReference(self, url, path, file):
		file_to_download = "/".join(url.split("/")[0:-1])+'/'
		file_to_download += file
		
		if( file.startswith('http') ):
			file_to_download = file
		if '--download' in sys.argv:
			utils.log(f"Downloading file: {file_to_download}")
		# check if file_to_download is a valid url
		if not file_to_download.startswith('http'):
			return False
		try: 
			file_to_download = file_to_download.replace('/./', '/')
			file_content = requests.get( file_to_download )
		except Exception as e:
			print( f"Error downloading file: {file_to_download}")
			print( e )
			return False
		
		if not os.path.exists(os.path.dirname(path+'/'+file)):
			try:
				os.makedirs(os.path.dirname(path+'/'+file))	
			except:
				pass
		if( is_valid_filename(path+'/'+file) ):
			with open(path + '/' + file, 'wb') as file:
				file.write(file_content.content)
		else:
			del file_content
			return False
		del file_content
		# open(path+'/'+file, 'wb').write(file_content.content)
		
		return True

	def validate( self, oas_file, commit_id ):
		try:
			with time_limit(10):
				parser = ResolvingParser( oas_file,  
						backend = 'openapi-spec-validator',
						strict=False )
			# Valid OAS file
			valid = 'true'
		except Exception as e:
			try:
				with time_limit(10):
					parser = BaseParser( oas_file, 
							backend = 'openapi-spec-validator',
							strict=False )
				valid = 'true'
			except Exception as deep_e:
				# Invalid OAS file
				# log = Log()
				# log.process='validator'
				# log.commit_id = commit_id
				# log.errorType = type(deep_e).__name__
				# log.msg = pymysql.escape_string( str(e) )
				# log.save()
				valid = 'false'
				if '-v' in sys.argv:
					utils.log(f"Invalid OAS file {oas_file} with commits.id={commit_id}")
		if '-v' in sys.argv:
			if valid == 'true':
				utils.log( f"Valid OAS file {oas_file} with commits.id={commit_id}")

		# utils.log(f"Valid OAS file with commits.id={commit_id}")
		update = f"UPDATE commits SET valid={valid} WHERE id={commit_id}"
		self.cursor.execute(update)
		self.connection.commit()
		

	def getFiles( self, limit = None ):
		mysql_select = """SELECT api.id, api.repo_name, api.owner, api.filepath, api.filename, api.updated_at, c.sha, c.id as commit_id FROM api_specs as api, commits as c 
							WHERE api.id = c.api_spec_id 
							AND c.valid IS NULL"""
		if limit is not None:
			mysql_select += " LIMIT "+str(limit)
		# rerun the JSON references extraction (added the code but not tested yet)
		# mysql_select = """SELECT api.id, api.repo_name, api.owner, api.filepath, api.filename, api.updated_at, c.sha, c.id as commit_id FROM api_specs as api, commits as c 
		# 					WHERE api.id = c.api_spec_id 
		# 					and valid=1 and filepath like '%.json'"""
		self.cursor.execute(mysql_select)
		mysql_result = self.cursor.fetchall()
		return mysql_result

	def setUrl(self, id, filepath, commit):
		mysql_select = f"""SELECT url FROM api_specs as api WHERE api.id = {id}"""
		self.cursor.execute(mysql_select)
		mysql_result = self.cursor.fetchone()

		try:
			if( mysql_result[0] ):
				url = mysql_result[0]
				splitUrl = url.split('/')
				retUrl = splitUrl[0]+'//'+splitUrl[2]+'/'+splitUrl[3]+'/'+splitUrl[4]+'/'+commit+'/'+filepath
				return retUrl
		except: 
			return False
		# return f"{self.github_base_url}{owner}/{repo_name}/{commit}/{filepath}"

def processRecord( record ):
	id, repo_name, owner, filepath, filename, updated_at, commit, commit_id = record
	validator = Validator()
	url = validator.setUrl( id, filepath, commit )
	if (url == False ): 
		# logModel = utils.Log()
		# logModel.process='validator'
		# logModel.commit_id = commit_id
		# logModel.errorType = "SettingUrl"
		# logModel.msg = f"Problem detected in validator.setUrl function APISpecsId: {id}"
		# logModel.save()
		utils.log(f"Problem detected in validator.setUrl function APISpecsId: {id}")
		return
	
	if len(os.path.dirname(filepath)) == 0:
		commit_filepath = f"commits/{commit}/{filename}"
	else:
		commit_filepath = f"commits/{commit}/{os.path.dirname(filepath)}/{filename}"

	try:
		validator.checkReferencies( url, owner, repo_name, commit_filepath, filename  )
	except FileNotFoundError as fnf:
		# logModel = utils.Log()
		# logModel.process='validator'
		# logModel.commit_id = commit_id
		# logModel.errorType = type(fnf).__name__
		# logModel.msg = pymysql.escape_string( str(fnf) )
		# logModel.save()
		utils.log( fnf )
		return

	validator.validate( validator.filePath(owner, repo_name, commit_filepath, filename), commit_id )
	
def handler(signal_received, frame):
	utils.log('SIGTERM detected. Exiting gracefully')
	exit(0)

if __name__ == "__main__":
	validator = Validator()
	# while( True ):
	# 	num_processes = int(os.getenv('PARALLEL_CPU_USAGE', mp.cpu_count()))
	# 	pool = mp.Pool( num_processes )
	# 	records = validator.getFiles()
	# 	tot_records = len(records)
	# 	print( f"Records to process: {tot_records}")
	# 	i = 0
	# 	for record in records:
	# 		i += 1
	# 		pool.apply_async( processRecord, args=(record))
	# 		if( i % 1000 == 0 ): 
	# 			utils.log(f"{i}/{tot_records}")
			
	# 	pool.close()
	# 	pool.join()

	# 	utils.log('Sleeping for 5 minutes')
	# 	time.sleep(5*60)

	while( True ):
		records = validator.getFiles(limit=1000)
		num_processes = int(os.getenv('PARALLEL_CPU_USAGE'))
		tot_records = len(records)
		print(f"Records to process: {tot_records}")
		if tot_records == 0:
			# wait 10 minutees before starting again
			print(f"Waiting 10 minutes before starting again")
			time.sleep(60*10)
			continue

		# Creare un pool di processi
		with mp.Pool(num_processes) as pool:
			pool.map(processRecord, records)
		# pool = mp.Pool(num_processes)
		# pool.map(processRecord, records)

		# # Attendere la terminazione di tutti i processi
		# pool.close()
		# pool.join()

		print("All processes have finished.")
