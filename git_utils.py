import sys
sys.path.append('./database/')
sys.path.append('./database/models/')
from utils import log
from github import Github
import github
from github.GithubException import GithubException 
from dotenv import load_dotenv
from mysql_lib import mysql_connect
import os
from pathlib import Path
import base64
from github.GithubException import UnknownObjectException
import requests
from commit import Commit
from lock import Lock
import time
from mysql_lib import mysql_connect
import calendar 
import random

load_dotenv()

output_folder = os.getenv('OUTPUT_FOLDER')

def checkGHRates(tkn):
	gh_token = Github(tkn)
	core_rate_limit = gh_token.get_rate_limit().core
	remaining = int( core_rate_limit.remaining )
	limit = int( core_rate_limit.limit)
	return remaining > 0
	
def getGithubTokens():
	connection = mysql_connect()
	cursor = connection.cursor()
	mysql_select = """SELECT token from github_tokens where active=1"""
	cursor.execute(mysql_select)
	mysql_result = cursor.fetchall()
	cursor.close()
	connection.close()
	tokens = []
	for token in mysql_result:
		tokens.append( token[0] )
	return tokens

def checkRepoExists( owner, repo_name):
	try:
		g = Github(token, per_page=100)
		repo = g.get_repo(owner+'/'+repo_name)
		return True
	except GithubException as e:
		if( e.status == 404 ):
			return False

def updateApiSpecsCreatedAt( owner, repo_name ):
	g = Github(token, per_page=100)
	repo = g.get_repo(owner+'/'+repo_name)
	sql = "UPDATE api_specs SET created_at=%s WHERE owner=%s and repo_name=%s"
	val = [repo.created_at, owner, repo_name]
	mysql_db = mysql_connect()
	cursor = mysql_db.cursor()
	cursor.execute(sql, val)
	mysql_db.commit()

def downloadFile( url, owner, repo_name, filepath, p_number=False, i=False, total=False ):
	# lock = Lock('downloadFile')
	if(p_number==False ): p_number_str = ''
	else: p_number_str = '#'+str(p_number)+'> '
	if(i!=False and total!=False): counter=f'({str(i)}/{str(total)})'
	else: counter = ''
	# log(f'{p_number_str} {counter} GET  {owner}/{repo_name}/{filepath}')
	# lock.acquire()
	try:
		path = Path(output_folder, owner, repo_name, filepath)
		path.parents[0].mkdir(parents=True, exist_ok=True)
		print( f"Downloading {url} to {path}")
		if is_valid_filename(path):
			file = requests.get(url)
			with path.open("wb") as target:
				target.write(file.content)
		# open(path, 'wb').write(file.content)
	except Exception as e:
		print( e )
	time.sleep(1)

def is_valid_filename(string):
    try:
        # Caratteri non permessi in un nome file
        invalid_chars = set('/\:*?"<>|')  # Lista di caratteri non permessi
        # Verifica se il nome file è valido e non contiene caratteri non permessi
        if os.path.basename(string) == string and len(string) > 0 and not any(char in invalid_chars for char in string):
            return True
        else:
            return False
    except:
        return False
	
def fileAlreadyExists(url, update_at):
    connection = mysql_connect()
    cursor = connection.cursor(buffered=True)

    mysql_select = """SELECT COUNT(id) FROM urls_to_check WHERE url=%s and updated_at=%s UNION SELECT COUNT(id) FROM api_specs WHERE url=%s and updated_at=%s"""
    mysql_values = [url, update_at, url, update_at]
    cursor.execute(mysql_select, mysql_values)
    mysql_result = cursor.fetchone()
    cursor.close()
    connection.close()

    if mysql_result[0] == 0: return False
    else: return True

def api_wait_search(github):
	limits = github.get_rate_limit()
	reset = limits.search.reset.replace(tzinfo=timezone.utc)
	now = datetime.now(timezone.utc)
	seconds = (reset - now).total_seconds()
	log(f'Rate limit exceeded: reset in {int(seconds)} seconds')
	if seconds > 0.0:
		time.sleep(seconds)


def get_commits( gh_token, owner, repo_name, filepath, api_spec_id, p_number=False ):
	if(p_number==False ): p_number_str = ''
	else: p_number_str = '#'+str(p_number)+'> '

	mysql_db = mysql_connect()
	cursor = mysql_db.cursor()
	folder, commits_filename = os.path.split(filepath)
	commits_general_path = output_folder + owner +'/'+ repo_name +'/commits/'
	commits_general_path = Path(commits_general_path)
	commits_general_path.mkdir(parents=True, exist_ok=True)
	# github.enable_console_debug_logging()
	repo = gh_token.get_repo(owner+'/'+repo_name)
	commits = repo.get_commits(path=filepath ) #path=filepath
	versions_count = 0
	commits_number = 0

	for commit in commits:
		commits_number += 1
		commit_date = commit.commit.author.date
		commit_path = Path.joinpath(commits_general_path, commit.sha+"/"+folder)
		content = repo.get_contents(filepath, commit.sha)
		if content != None and content.content != None:
			commit_path.mkdir(parents=True, exist_ok=True)
			versions_count += 1
			text = base64.b64decode(content.content).decode('utf-8')
			versioned_file = Path.joinpath(commit_path, commits_filename) 
			with versioned_file.open("w") as target:
				target.write(text)

			commitModel = Commit()
			commitModel.sha = commit.sha
			commitModel.commit_date = commit_date
			commitModel.api_spec_id = api_spec_id
			commitModel.save()
		
	log( f'{p_number_str}    {commits_number} commits and {versions_count} versions found')
	cursor.close()
	mysql_db.close()

#Return the sha of the last commit, 0 in case there no commits and -1 in case the repository doesn't exists
def get_last_commit( gh_token, owner, repo_name, filepath, proc_number ):
	try:
		if ( checkRepoExists(owner, repo_name) ):
			repo = gh_token.get_repo(owner+'/'+repo_name)
			commits = repo.get_commits(path=filepath )
			try:
				last_commit = commits[0].sha
			except Exception as deep_e:
				print( deep_e )
			return last_commit
		else:
			return -1
	except Exception as e:
		return 0

def buildGHUrl(owner, repo_name, sha, filepath):
	return f'https://raw.githubusercontent.com/{owner}/{repo_name}/{sha}/{filepath}'


if __name__ == "__main__":
	log(f'Generating in {output_folder}')