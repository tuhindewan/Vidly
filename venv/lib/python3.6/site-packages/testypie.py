import hashlib

import yaml
import os
from flask import Flask, request, Response
import logging
import requests
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote
from httplib2 import iri2uri


app = Flask(__name__)


BASEDIR = 'fixtures'


def url_to_filename(url):
    return quote(iri2uri(url), safe='') + '.yaml'


class literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(literal, literal_presenter)


class Cache(object):
    def __init__(self, basedir):
        self.basedir = basedir

    def __contains__(self, item):
        filename = os.path.join(self.basedir, url_to_filename(item))
        return os.path.exists(filename)

    def __setitem__(self, key, value):
        filename = os.path.join(self.basedir, url_to_filename(key))

        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        with open(filename, 'w') as cache_file:
            value['body'] = literal(value['body'])
            if 'request_body' in value:
                value['request_body'] = literal(value['request_body'])

            yaml.dump(value, cache_file, default_flow_style=False)
            logging.info('Wrote to: {}', filename)

    def __getitem__(self, item):
        filename = os.path.join(self.basedir, url_to_filename(item))

        with open(filename, 'r') as cache_file:
            value = yaml.safe_load(cache_file)

        return value


def create_incoming_headers(upstream_response):
    server_headers = {}
    for wanted_header in {'Content-Type', 'Location', 'Server'}:
        if wanted_header in upstream_response.headers:
            server_headers[wanted_header] = upstream_response.headers[wanted_header]
    return server_headers


def create_outgoing_headers(headers):
    client_headers = {}
    for wanted_header in {'Accept', 'Content-Type', 'X-Amz-Date', 'X-Amz-Security-Token', 'User-Agent', 'Content-Length', 'Authorization'}:
        if wanted_header in headers:
            client_headers[wanted_header] = headers[wanted_header]
    return client_headers


CACHE = Cache(BASEDIR)
HTTP = requests.Session()


def get_response(url, headers, method='get', body=None):

    cache_key = '{}-{}'.format(method.upper(), url)
    if body:
        cache_key += '-' + hashlib.md5(body).hexdigest()

    if cache_key not in CACHE:
        # Use requests to fetch the upstream URL the client wants
        outgoing_headers = create_outgoing_headers(headers)

        upstream = HTTP.request(
            method,
            url,
            allow_redirects=False,
            headers=outgoing_headers,
            data=body,
        )

        response_headers = create_incoming_headers(upstream)
        response = dict(code=upstream.status_code,
                        body=upstream.content.decode('utf-8'),
                        headers=response_headers)

        if body:
            response['request_body'] = body.decode('utf-8')

        CACHE[cache_key] = response

    return CACHE[cache_key]


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    response = get_response(request.url, request.headers, method=request.method)
    return Response(response=response['body'].encode('utf-8'),
                    status=response['code'],
                    headers=response['headers'])


if __name__ == "__main__":
    app.run()
