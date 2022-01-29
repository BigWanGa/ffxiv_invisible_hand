#!/usr/bin/python3
import json
from urllib import response
import requests
import time
import os

'''
思路：
1.获取可交易物品id list
2.遍历list：
    1.查询白银乡当前价格与历史价格
    2.查询猪区当前价格与历史价格
    3.存为json
'''

#初始化：获取可交易物品列表并缓存到本地，类型为list
s=requests.session()
if os.path.isfile("marketable.json"):
    fm=open("marketable.json","r")
    marketable_items=json.loads(fm.read())
    fm.close()
else:
    marketable_items=json.loads(s.get(url="https://universalis.app/api/marketable").content.decode())
    fm=open("marketable.json","w")
    fm.write(str(marketable_items))
    fm.close()

if len(marketable_items)!=0:
    print("可交易物品列表初始化完成，物品数："+str(len(marketable_items)))
else:
    print("可交易物品列表初始化失败，退出")
    exit()

#初始化：区服ID与API网址
datacenterid="莫古力"
worldid="白银乡"

url_now="https://universalis.app/api"
url_history="https://universalis.app/api/history"

#记录进度
item_count=len(marketable_items)
item_progress=1

time_start=time.time()

item_dict_list = {}

for itemid in marketable_items:
    #获取道具名称
    item_name=json.loads(s.get(url="https://cafemaker.wakingsands.com/item/"+str(itemid)+"?columns=Name").content.decode())["Name"]
    #打印进度
    print("<剩余"+str(time.strftime("%Hh%Mm%Ss",time.gmtime((time.time()-time_start)/item_progress*(item_count-item_progress))))+">["+str(item_progress)+"/"+str(item_count)+"]"+str(itemid)+" - "+str(item_name))
    item_progress+=1

    result_now=json.loads(s.get(url=url_now+"/"+str(worldid)+"/"+str(itemid)).content.decode())
    result_history=json.loads(s.get(url=url_history+"/"+str(worldid)+"/"+str(itemid)).content.decode())
    result_now_datacenter=json.loads(s.get(url=url_now+"/"+str(datacenterid)+"/"+str(itemid)).content.decode())

    item_dict = { 'item_id': itemid}
    item_dict['item_name'] = item_name
    item_dict['world_currently'] = result_now
    item_dict['world_history'] = result_history
    item_dict['datacenter_currently'] = result_now_datacenter
    item_dict_list[str(itemid)] = dict.copy(item_dict)
    item_dict.clear()
with open('data.json','w') as f:
    f.write(json.dumps(item_dict_list))
s.close()
