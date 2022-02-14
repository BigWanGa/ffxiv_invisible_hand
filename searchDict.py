import requests
import json

def searchDict(d, n, h):
    for key in d:
        if isinstance(d[key], dict):
            searchDict(d[key], n, h+'/'+key)
            #print('进入'+key+'\n')
        elif key == n:
            print(f'{h}/{key}:{d[key]}')

s=requests.session()
j = json.loads(s.get(url='https://xivapi.com/item/2').content.decode())
print(f'内容获取完成，长度：{len(j)}')
searchDict(j,'StackSize','')
print('搜索结束\n')