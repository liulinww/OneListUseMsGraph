# Author:  MoeClub.org, sxyazi

import json
import pickle
import hashlib

from dcache import Cache
from utils import path_format
from config import config
from urllib import request, parse


class _ItemInfo:
    def __init__(self):
        self.files = []
        self.folders = []
        self.is_file = False


class OneDrive():
    _request_headers = {'User-Agent': 'ISV|MoeClub|OneList/1.0',
                        'Accept': 'application/json; odata.metadata=none'}
    _request_headers={'Content-Type':'application/x-www-form-urlencoded'
            }
    def __init__(self):
        self.api_url = ''
        self.resource_id = ''
        self.access_token = ''
        self.refresh_token = config.token

    def get_access(self, resource='https://graph.microsoft.com/v1.0/me/'):
        res = self._http_request('https://login.microsoftonline.com/common/oauth2/v2.0/token', method='POST', data={
            'client_id': 'ea2b36f6-b8ad-40be-bc0f-e5e4a4a7d4fa',
            'client_secret': 'h27zG8pr8BNsLU0JbBh5AOznNS5Of5Y540l/koc7048=',
            'redirect_uri': 'http://localhost/onedrive-login',
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token',
        })

        self.access_token = res['access_token']
        self.refresh_token = res['refresh_token']

        if not self.access_token:
            print('Unauthorized')
            exit(1)

    def get_resource(self):
        self.api_url = 'https://graph.microsoft.com/v1.0/me'
        self.resource_id = 'https://graph.microsoft.com/v1.0/me/'

    def list_items(self, path=''):
        url = '%s/drive/root?$expand=children' % (
            self.api_url)
        if len(path)>1:
            url = '%s/drive/root:/%s?$expand=children' % (
            self.api_url, parse.quote(path_format(path)))
        
        
        res = self._http_request(url)

        info = _ItemInfo()
        self._append_item(info, res)

        if 'children' in res:
            for children in res['children']:
                self._append_item(info, children)

        if info.files and not info.folders:
            info.is_file = True
        return info

    def list_all_items(self, path='/'):
        ret = _ItemInfo()
        tasks = [{'full_path': path}]

        while len(tasks) > 0:
            c = tasks.pop(0)

            tmp = self.list_items(c['full_path'])
            tasks += tmp.folders[1:]

            ret.files += tmp.files
            ret.folders += tmp.folders[1:]

        if ret.files and not ret.folders:
            ret.is_file = True
        return ret

    def list_items_with_cache(self, path='/', flash=False):
        path = path_format(path)
        key = ('tmp:' + path) if flash else path

        if not Cache.has(key):
            if flash:
                Cache.set(key, self.list_items(path), 10)
            else:
                print('missing: %s' % path)

                info = self.list_items(path)
                if info.is_file:
                    Cache.set(key, info, config.metadata_cached_seconds)
                else:
                    Cache.set(key, info, config.structure_cached_seconds)

        return Cache.get(key)

    def _http_request(self, url, method='GET', data={}):
        headers = self._request_headers.copy()
        if self.access_token:
            headers['Authorization'] = "Bearer " + self.access_token
        data = parse.urlencode(data).encode('utf-8')
        res = json.loads(request.urlopen(request.Request(
            url, method=method, data=data, headers=headers)).read().decode('utf-8'))

        if 'error' in res:
            raise Exception(res['error']['message'])
        return res

    def _append_item(self, info, item):
        if 'path' not in item['parentReference']:
            path = item['name'] = '/'
        else:
            path = item['parentReference']['path'][12:] or '/'

        dic = {
            'name': item['name'],
            'size': item['size'],
            'hash': self._get_item_hash(item),
            'folder': path,
            'full_path': path_format(path + '/' + item['name']),
            'updated_at': item['lastModifiedDateTime']
        }
        if '@microsoft.graph.downloadUrl' in item:
            dic['download_url'] = item['@microsoft.graph.downloadUrl']

        if 'file' in item:
            info.files.append(dic)
        else:
            info.folders.append(dic)

    def _get_item_hash(self, item):
        dic = {
            'name': item['name'],
            'size': item['size'],
            'parentReference': item['parentReference'],
            'lastModifiedDateTime': item['lastModifiedDateTime']
        }

        if 'file' in item:
            dic['file'] = item['file']
        else:
            dic['folder'] = item['folder']

        return hashlib.md5(pickle.dumps(dic)).hexdigest()
