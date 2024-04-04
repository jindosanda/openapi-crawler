import sys
import time
import random
import os
sys.path.append('./database/')
sys.path.append('./database/models/')
from api_query import ApiQuery
from github.GithubException import RateLimitExceededException, GithubException
import multiprocessing as mp
from signal import signal, SIGTERM, SIGINT
from lock import Lock
from counter import Counter
from pipeline import Pipeline
from git_utils import api_wait_search, get_commits, downloadFile, fileAlreadyExists, updateApiSpecsCreatedAt, checkRepoExists, get_last_commit, buildGHUrl
from utils import log
from mysql_lib import mysql_connect
from datetime import datetime, timezone, date
import traceback
import chardet

class Curiosity(Pipeline):
    def __init__(self):
        super().__init__()

    def checkFileContentAndUpdate(self, id, url,  oas_file, owner, repo_name, last_commit, filepath, proc_number):
        try:
            f = open(oas_file, "r", errors='ignore')
            try:
                file_content = f.read()
            except UnicodeDecodeError:
                with open(oas_file, 'rb', errors='ignore') as f:
                    raw_data = f.read(10000)  # leggi i primi 10000 byte
                    result = chardet.detect(raw_data)
                    encoding = result['encoding']
                with open(oas_file, 'r', encoding=encoding) as f:
                    file_content = f.read()
            f.close()
            if( file_content.startswith('404: Not Found') ):
                print(file_content, oas_file)
                new_url = buildGHUrl(owner, repo_name, last_commit, filepath)
                downloadFile( new_url, owner, repo_name, filepath, proc_number )
                
                # update the url field when is different (assuming revert case)
                if( url != new_url ):
                    update_mysql_db = mysql_connect()
                    update_cursor = update_mysql_db.cursor()
                    update_sql = f"UPDATE api_ace_crawler.urls_to_check set url='{new_url}' where id={id}"
                    if '-v' in sys.argv: print(update_sql)
                    update_cursor.execute(update_sql)
                    update_mysql_db.commit()
                    update_cursor.close()
                    update_mysql_db.close()
        except IOError:
            print("IO error on file", oas_file)

            
    def process( self ):
        counter = Counter()
        counter.name = 'curiosity'
        while True:
            try:
                counter.counter = 0
                counter.save()
                mysql_db = mysql_connect()
                cursor = mysql_db.cursor()
                sql_count = "SELECT count(*) as total FROM urls_to_check"
                cursor.execute(sql_count)
            
                total = int(cursor.fetchone()[0])
                num_processes = len(self.gh)
                step = -(-total // num_processes)
                
                pool = mp.Pool( num_processes )
                
                limit_from = 0
                processes = {}
                p_number = 0

                if total < num_processes:
                    self.processRecords(0, self.gh[0], counter, 0, total)
                else:    
                    for p_number in range(num_processes):
                        limit_to = min(limit_from + step, total)

                        gh = self.gh[p_number]
                        pool.apply_async(self.processRecords, args=(p_number, gh, counter, limit_from, limit_to))
                        limit_from = limit_to
                
                pool.close()
                pool.join()
                cursor.close()
                mysql_db.close()

                log('No data to check. Waiting 1 minute')
                
                time.sleep(60)
            
            except RateLimitExceededException as e:
                api_wait_search(g)

    def processRecords( self, proc_number, gh, counter, limit_from, limit_to ):
        p_number = '#'+str(proc_number)+'> '
        mysql_db = mysql_connect()
        cursor = mysql_db.cursor()
        sql_url_to_check = f"SELECT * FROM urls_to_check ORDER BY id LIMIT {limit_from},{limit_to}"

        cursor.execute(sql_url_to_check)
        files = cursor.fetchall()

        i = 0
        for f in files:
            try: 
                id,repo_name,owner,filepath,filename,url,github_query_id, created_at,updated_at = f[0],f[1],f[2],f[3],f[4],f[5],f[6],f[7],f[8]
                log(p_number+ f'  {owner}/{repo_name}')
                last_commit = get_last_commit( gh, owner, repo_name, filepath, proc_number )
                
                # The repo doesn't exists anymore
                if( type(last_commit)==int and last_commit < 0 ):
                    continue
                
                oas_file = self.filePath(owner, repo_name, filepath, filename)

                if(not os.path.exists(oas_file)):
                    downloadFile( url, owner, repo_name, filepath, proc_number )
                
                self.checkFileContentAndUpdate(id, url, oas_file, owner, repo_name, last_commit, filepath, proc_number)

                conn = mysql_connect()
                csr = conn.cursor()
                sql = "SELECT id, updated_at, created_at FROM api_specs WHERE owner=%s AND repo_name=%s AND filepath=%s LIMIT 1"
                val = [owner, repo_name, filepath]
                csr.execute(sql, val)
                select_result = csr.fetchone()
                csr.close()
                conn.close()
                queryType = None
                
                query = ""
                if( select_result == None ):
                    queryType = 'insert'
                    query = "INSERT INTO api_specs (repo_name, owner, filepath, filename, url, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    val = [repo_name, owner, filepath, filename, url, created_at, updated_at]
                else:
                    queryType = 'update'
                    api_spec_id, api_specs_updated_at, api_specs_created_at = select_result[0], select_result[1], select_result[2]
                    self.updateProcessedAt( api_spec_id )
                    
                    if( updated_at != api_specs_updated_at):
                        query = "UPDATE api_specs SET url=%s, updated_at=%s WHERE id=%s"
                        val = [url, updated_at, api_spec_id]
                    if( api_specs_created_at == None ):
                        log(p_number+ f'  Retrieving created_at field for repository {owner}/{repo_name}')
                        if( checkRepoExists(owner, repo_name) != False ):
                            updateApiSpecsCreatedAt( owner, repo_name )
                        else:
                            self.setApiSpecDeleted( api_spec_id )

                if(queryType is not None or len(query)>0 ):
                    conn = mysql_connect()
                    csr = conn.cursor()
                    csr.execute(query, val)
                    if queryType == 'insert': api_spec_id = csr.lastrowid
                    conn.commit()
                    conn.close()
                    csr.close()
                    
                if( api_spec_id <= 0 ): log(p_number+ f'get_commits: id specified is {api_spec_id}')
                
                self.updateGHQueryAssocation( github_query_id, api_spec_id )
                
                attempts = 0
                while(attempts < 2):
                    try:
                        get_commits(gh, owner, repo_name, filepath, api_spec_id, proc_number)
                        break
                    except GithubException as e:
                        print("GithubException handled: ")
                        print(e)
                        if( e.status == 404 ):
                            if( checkRepoExists(owner, repo_name) == False ):
                                self.setApiSpecDeleted( api_spec_id )
                            break
                        attempts+=1
                        time.sleep(3)
                        
                counter.counter += 1
                counter.save()
                sql = "DELETE FROM urls_to_check WHERE id=%s"
                val = [id]
                conn = mysql_connect()
                csr = conn.cursor()
                csr.execute(sql, val)
                conn.commit()
                conn.close()
                csr.close()
            except Exception:
                traceback.print_exc()
            cursor.close()
            mysql_db.close()
        
    def updateGHQueryAssocation( self, github_query_id, api_spec_id ):
        api_query = ApiQuery()
        api_query.github_query_id = github_query_id
        api_query.api_spec_id = api_spec_id
        api_query.save()

    def updateProcessedAt( self, id ):
        mysql_db = mysql_connect()
        cursor = mysql_db.cursor()
        current_dt = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        sql = "UPDATE api_specs SET processed_at=%s WHERE id=%s"
        val = [current_dt, id]
        cursor.execute(sql, val)
        mysql_db.commit()
        cursor.close()
        mysql_db.close()
    
    def setApiSpecDeleted( self, api_spec_id ):
        mysql_db = mysql_connect()
        cursor = mysql_db.cursor()
        sql = "UPDATE api_specs SET deleted=%s WHERE id=%s"
        val = [1, api_spec_id]
        cursor.execute(sql, val)
        mysql_db.commit()

def handler(signal_received, frame):
    log('SIGTERM detected. Exiting gracefully')
    lock = Lock('downloadFile')
    lock.release()
    exit(0)

if __name__ == "__main__":
    curiosity = Curiosity()
    curiosity.process()

