from dotenv import load_dotenv
import os 
from github import Github
from database.mysql_lib import mysql_connect
import sys

class Pipeline():
	max_file_size = 0
	tables = {
		'specifications': 'api_specs',
		'methods': 'methods',
		'parameters': 'parameters',
		'commits': 'commits',
		'responses': 'responses'
	}
	gh = []

	def __init__( self ):
		load_dotenv()
		tokens = self.getGithubTokens()
		i = 0
		for token in tokens:
			self.gh.append( Github( token[0], per_page=100 ) )
			i+=1
		self.max_file_size = int(os.getenv('MAX_FILE_SIZE'))
		self.output_folder = os.getenv('OUTPUT_FOLDER')
		self.github_base_url = os.getenv('GITHUB_BASE_URL')

	def getGithubTokens( self ):
		connection = mysql_connect()
		cursor = connection.cursor()
		mysql_select = """SELECT token from github_tokens where active=1"""
		cursor.execute(mysql_select)
		mysql_result = cursor.fetchall()
		cursor.close()
		connection.close()
		return mysql_result

	def filePath(self, owner, repo, filepath, filename):
		if os.path.isabs( filepath ):
			return( os.path.abspath( filepath+'/'+filename ) )
		else:	
			relative_path = f"{self.output_folder}{owner}/{repo}/{os.path.dirname(filepath)}/{filename}"
			absolute_path = os.path.abspath( relative_path )
			return absolute_path
		
	def fileDir(self, repo, owner, filepath, absolute=False):
		relative_path = f"{self.output_folder}{owner}/{repo}/{os.path.dirname(filepath)}"
		if absolute == True:
			return os.path.abspath( relative_path )
		else:	
			return relative_path
