# npm install -g @apidevtools/swagger-cli
import sys, os
sys.path.append('./database/')
sys.path.append('./database/models/')
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
from mysql_lib import mysql_connect
from pipeline import Pipeline
from commit import Commit
from datetime import datetime
import multiprocessing as mp

class Bundler(Pipeline):
	def getFiles( self ):
			connection = mysql_connect()
			cursor = connection.cursor(buffered=True)
			mysql_select = """	SELECT repo_name, owner, filename, filepath, sha, c.id as commit_id FROM api_ace_crawler.commits as c
								LEFT JOIN api_specs as a ON a.id=c.api_spec_id
								WHERE bundled_at is null"""
			
			cursor.execute(mysql_select)
			mysql_result = cursor.fetchall()
			cursor.close()
			connection.close()
			return mysql_result

def runBundle( repo_name, owner, filename, filepath, sha, commit_id ):
	bundler = Bundler()
	basepath = bundler.fileDir(repo_name, owner, filepath, True)+'/commits/'+sha+'/'
	src_file = basepath+filename
	filename_splitted = os.path.splitext( filename )
	bundled_file = basepath+filename_splitted[0]+'.bundled'+filename_splitted[1]
	command = f"swagger-cli bundle {src_file} -o {bundled_file}"
	result = os.system( command )
	if result == 0:
		commit = Commit()
		commit.id = commit_id
		commit.bundled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		commit.save()

if __name__ == "__main__":
	bundler = Bundler()
	pool = mp.Pool(int( os.getenv('PARALLEL_CPU_USAGE' )))
	records = bundler.getFiles()
	for commit in records:
		pool.apply_async( runBundle, args=(commit))
	pool.close()
	pool.join()