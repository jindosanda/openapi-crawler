import sys, os
sys.path.append('./database/')
sys.path.append('./database/models/')
from urls_to_check import UrlToCheck
from dotenv import load_dotenv
from mysql_lib import mysql_connect
import ntpath
import datetime
from utils import log
import time
from counter import Counter

load_dotenv()

output_folder = os.getenv('OUTPUT_FOLDER')

def getSpecificationsFromDB():
    connection = mysql_connect()
    cursor = connection.cursor(buffered=True)
    dt_limit = datetime.datetime.today()-datetime.timedelta(days = 15)
    mysql_select = """SELECT id, repo_name, owner, filepath, filename, url, created_at, updated_at 
                      FROM api_specs 
                      WHERE (processed_at <= %s OR processed_at IS NULL) AND deleted=0"""
    val = [ dt_limit.strftime('%Y-%m-%d') ]
    cursor.execute(mysql_select, val)
    
    mysql_result = cursor.fetchall()
    cursor.close()
    connection.close()
    return mysql_result

def getLastQueryUsed( id ):
    connection = mysql_connect()
    cursor = connection.cursor(buffered=True)
    mysql_select = """SELECT github_query_id FROM api_ace_crawler.api_queries where api_spec_id=%s order by updated_at desc limit 1;"""
    val = [ id ]
    cursor.execute(mysql_select, val)
    mysql_result = cursor.fetchone()
    cursor.close()
    connection.close()
    if(mysql_result == None):
        log(f"ERROR: SELECT github_query_id FROM api_ace_crawler.api_queries where api_spec_id=%s order by updated_at desc limit 1; returns None")
        return None
    return mysql_result[0]

def update( records ):
    total = 0

    log(f'{len(records)} records candidates for update')
    counter = Counter()
    counter.name = 'updater'
    counter.counter = 0
    for record in records:
        counter.counter += 1
        counter.save()
        
        id, repo_name, owner, filepath, filename, url, created_at, updated_at = record[0], record[1], record[2], record[3], record[4], record[5], record[6], record[7]
        # Retrieve the last query used for the api
        query_id = getLastQueryUsed( id )
        commits_folder, filename = ntpath.split(output_folder+owner+'/'+repo_name+'/'+filepath)
        urltocheck = UrlToCheck()
        urltocheck.repo_name = repo_name
        urltocheck.owner = owner
        urltocheck.filepath = filepath
        urltocheck.filename = filename
        urltocheck.url = url
        urltocheck.github_query_id = query_id
        if( created_at != None ):
            urltocheck.created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
        if( updated_at != None ):
            urltocheck.updated_at = updated_at.strftime("%Y-%m-%d %H:%M:%S")
        urltocheck.save()
        
        total = total + 1
        log(f'  {total}/{len(records)} - {owner}/{repo_name}')

if __name__ == '__main__':
    while True:
        update( getSpecificationsFromDB() )
        log(f'Waiting 5 minutes')
        time.sleep(5*60)