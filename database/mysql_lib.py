import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import time

load_dotenv()

def mysql_connect():
    while ( True ):
        try:
            mysql_db = mysql.connector.connect(
                host=os.getenv('MYSQL_HOST'),
                user=os.getenv('MYSQL_USER'),
                password=os.getenv('MYSQL_PASSWORD'),
                database=os.getenv('MYSQL_DATABASE'),
                auth_plugin='mysql_native_password'
            )
            return mysql_db
        except Error as e:
            print("Error while connecting to MySQL", e)
            print("Waiting 1 seconds to reconnect")
            time.sleep(1)