import sys
sys.path.append('./database/')
sys.path.append('./database/models/')
from urls_to_check import UrlToCheck
import time
from datetime import date
from database.mysql_lib import mysql_connect
from utils import log
import traceback 
from git_utils import fileAlreadyExists, downloadFile
from pipeline import Pipeline
from github import Github
import multiprocessing as mp

class PathFinder( Pipeline ):
    
    def __init__(self):
        super().__init__()
        
    def saveCounter(self, name, counter):
        connection = mysql_connect()
        cursor = connection.cursor()
        
        mysql_delete = """DELETE FROM counters WHERE name=%s"""
        mysql_values = [name]
        cursor.execute(mysql_delete, mysql_values)
        
        mysql_insert = """INSERT INTO counters(name, counter) VALUES(%s, %s)"""
        mysql_values = [name, counter]
        cursor.execute(mysql_insert, mysql_values)
        connection.commit()
        cursor.close()
        connection.close()

    def getCounter(self, name):
        connection = mysql_connect()
        cursor = connection.cursor()
        mysql_select = """SELECT counter FROM counters WHERE name=%s"""
        mysql_values = [name]
        cursor.execute(mysql_select, mysql_values)
        mysql_result = cursor.fetchone()
        cursor.close()
        connection.close()
        return mysql_result[0] if mysql_result != None else None

    def getActiveGithubQueries( self ):
        connection = mysql_connect()
        cursor = connection.cursor()
        mysql_select = """SELECT id, query FROM github_queries WHERE active=1"""
        cursor.execute(mysql_select)
        mysql_result = cursor.fetchall()
        cursor.close()
        connection.close()
        return mysql_result

    def process(self):
        today = date.today().strftime("%Y%m%d")
        total = 0
        mysql_db = mysql_connect()
        cursor = mysql_db.cursor()

        queries = self.getActiveGithubQueries()
        procjects_excude_list = ['USI-INF-']

        log(f'{len(self.gh)} GitHub tokens in use')
        
        try:
            pool = mp.Pool(len(self.gh))
            while True:
                current_counter = self.getCounter('pathfinder_crawl')
                start = current_counter if current_counter != None and current_counter < self.max_file_size else 1
                step = len(self.gh) * 25

                for size in range(start, self.max_file_size + 1, step):
                    size_from = size
                    processes = {}
                    for i, gh in enumerate(self.gh, start=1):
                        size_to = size_from + int(step / len(self.gh))
                        processes[i] = pool.apply_async(self.findProjects, args=([i, gh, size_from, size_to, queries, procjects_excude_list]))
                        size_from += int(step / len(self.gh))

                    for p in processes.values():
                        p.get()  

                    self.saveCounter('pathfinder_crawl', size + step)

                time.sleep(60*60)

        except Exception as e:
            traceback.print_exception(*sys.exc_info())
            time.sleep(5*60)
        finally:
            pool.close()
            pool.join()


                
    def findProjects( self, proc_number, gh_account, size_from, size_to, queries, procjects_excude_list ):
        p_number = '#'+str(proc_number)+'> '
        for q in queries:
            try:
                query_id = q[0]
                query_string = q[1]+' size:' + str(size_from) + '..' + str( size_to )
                log( p_number + query_string )
                # GitHub query
                files = gh_account.search_code(query=query_string)
                i = -1
                log( p_number + 'Total files: ' + str(files.totalCount) )
                projectsFound = 0
                start = time.time()
                for f in files:
                    i += 1
                    exclude_file = False
                    project_full_name = f.repository.full_name
                    for project in procjects_excude_list:
                        if( project in project_full_name ): 
                            exclude_file = True
                            break
                    if( exclude_file ): continue

                    if fileAlreadyExists( f.download_url, f.repository.updated_at ) == False:
                        urltocheck = UrlToCheck()
                        urltocheck.repo_name = f.repository.name
                        urltocheck.owner = f.repository.owner.login
                        urltocheck.filepath = f.path
                        urltocheck.filename = f.name
                        urltocheck.url = f.download_url
                        urltocheck.github_query_id = query_id
                        urltocheck.created_at = f.repository.created_at
                        urltocheck.updated_at = f.repository.updated_at
                        urltocheck.save()
                        api_spec_id = urltocheck.id
                        downloadFile( f.download_url, f.repository.owner.login, project_full_name, f.path, proc_number, i, files.totalCount )
                        projectsFound += 1
                end = time.time()
                time_interval = (end - start)/60 #in minutes
                avg_speed = projectsFound / time_interval
                log(f'{p_number} AVG speed: {avg_speed} projects/minute | time interval: {time_interval} minutes')
            except Exception as rle:
                print( p_number + str(rle) )
                time.sleep(30)


if __name__ == "__main__":
    pathfinder = PathFinder()
    pathfinder.process()

