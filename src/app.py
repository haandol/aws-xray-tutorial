import os
import json
import atexit
import random
import logging
import traceback

import boto3
import falcon
import psycopg2 as pg2
from psycopg2 import pool
from aws_xray_sdk.core.models import http
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

xray_recorder.configure(
    sampling=False,
    service='xray-tutorial',
    daemon_address='localhost:2000',
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('xray-tutorial')

client = boto3.client('secretsmanager')
random.seed(17)

SECRET_ARN = 'arn:aws:secretsmanager:ap-northeast-2:929831892372:secret:RdsClusterDemoSecret8F16788-mmSp7Q22t6WR-17fNio'
PG_POOL = None
CHAOTIC_THRESHOLD = 20


def get_conn_pool():
    resp = client.get_secret_value(SecretId=SECRET_ARN)
    secret_value = json.loads(resp['SecretString'])

    return pool.SimpleConnectionPool(
        1, 5, 
        user=secret_value['username'],
        password=secret_value['password'],
        host=secret_value['host'],
        port=secret_value['port'],
        database=secret_value['dbname'],
    )


@atexit.register
def exit_handler():
    if PG_POOL:
        logger.info('closing all open connections...')
        PG_POOL.closeall()


class XRayMiddleWare(object):
    def process_request(self, req, resp):
        segment = xray_recorder.begin_segment(req.path[1:])
        req.context.segment = segment
        segment.put_http_meta(http.URL, req.path)
        segment.put_http_meta(http.METHOD, req.method)

    def process_response(self, req, resp, resource, req_succeeded):
        req.context.segment.put_http_meta(http.STATUS, resp.status.split()[0])
        req.context.segment = None
        xray_recorder.end_segment()


class ChaoticMiddleWare(object):
    def process_resource(self, req, resp, resource, params):
        if 'init' in req.path:
            return

        if random.randint(1, 100) < CHAOTIC_THRESHOLD:
            raise falcon.HTTPBadRequest('Chaos got your request')


class BaseResource(object):
    def get_params(self, req):
        body = req.stream.read()
        if not body:
            raise falcon.HTTPBadRequest('Empty request body')
        return json.loads(body.decode('utf-8'))

    def get_conn(self):
        global PG_POOL

        if not PG_POOL:
            PG_POOL = get_conn_pool()

        try:
            return PG_POOL.getconn()
        except (Exception, pg2.DatabaseError) as e:
            traceback.print_exc()
            raise falcon.HTTPBadRequest('Error while connecting to PostgreSQL')


class PingResource(object):
    def on_get(self, req, resp):
        resp.status = falcon.HTTP_OK
        resp.body = 'pong'


class InitResource(BaseResource):
    def on_post(self, req, resp):
        conn = self.get_conn()
        with xray_recorder.in_subsegment('create table') as subsegment:
            with conn.cursor() as cursor:
                sql = """CREATE TABLE posts ( \
                    id serial PRIMARY KEY, \
                    username VARCHAR(256), \
                    title VARCHAR(256), \
                    content TEXT
                );"""
                cursor.execute(sql)
                conn.commit()
            subsegment.put_metadata('sql', sql)
        PG_POOL.putconn(conn)

        resp.status = falcon.HTTP_OK
        resp.body = 'ok'

    def on_delete(self, req, resp):
        conn = self.get_conn()
        with xray_recorder.in_subsegment('drop table') as subsegment:
            with conn.cursor() as cursor:
                sql = """DROP TABLE posts"""
                cursor.execute(sql)
                conn.commit()
            subsegment.put_metadata('sql', sql)
        PG_POOL.putconn(conn)

        resp.status = falcon.HTTP_OK
        resp.body = 'ok'


class PostsResource(BaseResource):
    def on_post(self, req, resp):
        params = self.get_params(req)
        title = params.get('title', '')
        content = params.get('content', '')
        if not (title and content):
            raise falcon.HTTPBadRequest('title and content should not be empty')

        username = params.get('username', '')
        if not username:
            raise falcon.HTTPBadRequest('username should not be empty')

        req.context.segment.put_annotation('username', username)

        conn = self.get_conn()
        with xray_recorder.in_subsegment('create post') as subsegment:
            with conn.cursor() as cursor:
                sql = f"INSERT INTO posts (title, content, username) VALUES ('{title}', '{content}', '{username}')"
                cursor.execute(sql)
                conn.commit()
            subsegment.put_metadata('sql', sql)
        PG_POOL.putconn(conn)

        resp.status = falcon.HTTP_OK
        resp.body = 'ok'


class PostResource(BaseResource):
    def on_get(self, req, resp, pid):
        conn = self.get_conn()
        req.context.segment.put_annotation('post_id', pid)
        with xray_recorder.in_subsegment('get post') as subsegment:
            with conn.cursor() as cursor:
                sql = f'SELECT * FROM posts WHERE id={pid}'
                cursor.execute(sql)
                posts = cursor.fetchall()
            subsegment.put_metadata('sql', sql)
        PG_POOL.putconn(conn)

        resp.status = falcon.HTTP_OK
        resp.body = json.dumps(posts)

    def on_delete(self, req, resp, pid):
        conn = self.get_conn()
        req.context.segment.put_annotation('post_id', pid)
        with xray_recorder.in_subsegment('delete post') as subsegment:
            with conn.cursor() as cursor:
                sql = f'DELETE FROM posts WHERE id={pid}'
                cursor.execute(sql)
                conn.commit()
            subsegment.put_metadata('sql', sql)
        PG_POOL.putconn(conn)

        resp.status = falcon.HTTP_OK
        resp.body = 'ok'


api = falcon.API(middleware=[XRayMiddleWare(), ChaoticMiddleWare()])
api.add_route('/', PingResource())
api.add_route('/init', InitResource())
api.add_route('/posts', PostsResource())
api.add_route('/posts/{pid:int}', PostResource())