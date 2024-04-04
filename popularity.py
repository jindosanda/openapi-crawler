import sys, time
sys.path.append('./')
sys.path.append('./database/')
sys.path.append('./database/models/')
from github import Github
import multiprocessing as mp
from pipeline import Pipeline
from git_utils import getGithubTokens
from utils import log
from mysql_lib import mysql_connect
from api_specs_popularity import ApiSpecsPopularity


class Popularity(Pipeline):
    def __init__(self):
        super().__init__()

    def getAPIs(self):
        connection = mysql_connect()
        cursor = connection.cursor()
        if( '--continue' in sys.argv ):
            if( len(sys.argv) >= 3 ):
                date = sys.argv[2]
                mysql_select = f""" SELECT owner, repo_name
                                    FROM api_specs a
                                    where deleted=0 and CONCAT(owner,'_',repo_name) not in ( select CONCAT(owner,'_',repo_name) from api_specs_popularity where DATE(created_at)>='{date}' )
                                    group by owner, repo_name;"""
            else:
                print("date is missing")
                sys.exit()
        else:
            mysql_select = """  SELECT owner, repo_name
                            FROM api_specs a
                            where deleted=0
                            group by owner, repo_name;"""
        cursor.execute(mysql_select)
        mysql_result = cursor.fetchall()
        cursor.close()
        connection.close()
        return mysql_result
    
    def setAsDeleted( self, owner, repo_name ):
        connection = mysql_connect()
        cursor = connection.cursor()
        update = f"UPDATE api_specs a SET deleted=1 where owner='{owner}' and repo_name='{repo_name}';"
        if( '-v' in sys.argv ): print( update )
        cursor.execute(update)
        connection.commit()
        cursor.close()
        connection.close()

    def getInfo(self, owner, repo, token):
        try:
            repo = token.get_repo(owner+'/'+repo)
        except Exception as e:
            print( e )
            if( '404 {"message": "Not Found"' in str(e) or 
                '403 {"message": "Repository access blocked"' in str(e) or 
                '451 {"message": "Repository access blocked",' in str(e) ): 
                self.setAsDeleted( owner, repo )
            return False
        info = {}
        info['forks'] = repo.forks_count 
        info['stars'] = repo.stargazers_count
        info['watching'] = repo.subscribers_count
        return info

    def saveInfo( self, owner, repo_name, info ):
        connection = mysql_connect()
        cursor = connection.cursor()
        sql = f"""SELECT id from api_specs where owner='%s' and repo_name='%s';"""
        cursor.execute( sql % (owner, repo_name) )
        ids = cursor.fetchall()
        cursor.close()
        connection.close()
        for record in ids:
            id = record[0]
            pop = ApiSpecsPopularity()
            pop.api_spec_id = id
            pop.owner = owner
            pop.repo_name = repo_name
            pop.forks = info['forks']
            pop.stars = info['stars']
            pop.watching = info['watching']
            pop.updated_at = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
            pop.save()

    def process_apis(self, apis, token):
        for api in apis:
            owner, repo = api
            try:
                info = self.getInfo(owner, repo, token)
                if info:
                    self.saveInfo(owner, repo, info)
            except Exception as e:
                print(e)
                time.sleep(5 * 60)


if __name__ == "__main__":
    start = time.time()
    pop = Popularity()
    apis = pop.getAPIs()
    print(f"Total APIs selected: {len(apis)}")
    str_tokens = getGithubTokens()
    tokens = []
    for token in str_tokens:
        tokens.append( Github(token, per_page=100) )
    
    # Divide the APIs among the tokens
    apis_per_token = len(apis) // len(tokens)
    processes = []

    for i, token in enumerate(tokens):
        start_index = i * apis_per_token
        end_index = start_index + apis_per_token
        if i == len(tokens) - 1:
            end_index = len(apis)

        process = mp.Process(target=pop.process_apis, args=(apis[start_index:end_index], token))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    print(f"Total time: {time.time() - start} seconds")