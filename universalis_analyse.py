#!/usr/bin/python3
import json
from re import T
import numpy as np
import time
import requests
import os

'''
思路：
    1.每个道具分析一次
    2.对全区挂售价取最低的N个计算平均值，记录标准差
    3.对本区成交价取最近的M个计算平均值，记录标准差
    4.对本区挂售价取最低的X个计算平均值，记录标准差，记录挂售价平均值与成交价平均值的差值
    5.对于挂售价，若有单个数据是其余数据的10倍，则剔除
    6.对于成交价，若由单个数据是其余数据的1/10倍，则剔除
    7.以本区成交价平均值与全区挂售价平均值对比得出利润率、单价差
    8.NQ与HQ作为两种道具对待
'''

#设定要进行分析的服务器名称与大区名称
world_name = '白银乡'
datacenter_name = '莫古力'

#设定分析参数
order_time = 2592000        #只看多少秒内的成交记录，2592000是30天
order_datacenter_cur = 4    #全区挂售价只看最低的前几
order_world_his = 5         #本服成交价只看最近的前几
order_world_cur = 4         #本服挂售价只看最低的前几

#初始化csv文件
f_path = f'{world_name}.csv'

c1 = '物品ID'
c2 = '物品名称'
c3 = '全区挂售价'
c4 = '全区挂售价标准差'
c5 = '本服成交价'
c6 = '本服成交价标准差'
c7 = '本服挂售价'
c8 = '本服挂售价标准差'
c9 = '本服挂售价与成交价差值'
c10 = '利润率'
c11 = '单价差'
c12 = '本服近一个月成交次数'
c13 = '本服近一个月成交数量'

f_column = f'{c1},{c2},{c3},{c4},{c5},{c6},{c7},{c8},{c9},{c10},{c11},{c12},{c13}\n'
with open(f_path,'w') as f:
    f.write(f_column)
#初始化csv文件完毕

#载入数据
d_path = 'data.json'
with open(d_path) as d_file:
    d=json.loads(d_file.read())

#获取可交易物品列表并缓存到本地，类型为list
s=requests.session()
if os.path.isfile("marketable.json"):
    with open('marketable.json') as fm:
        marketable_items = json.loads(fm.read())
else:
    marketable_items=json.loads(s.get(url="https://universalis.app/api/marketable").content.decode())
    with open('marketable.json','w') as fm:
        fm.write(str(marketable_items))
if (item_count := len(marketable_items)) != 0:
    print(f"可交易物品列表初始化完成，物品数：{item_count}")
else:
    print("可交易物品列表初始化失败，退出")
    exit()

time_start = time.time()
item_progress = 1

#分析物品的函数
def analyse(_item, isHQ):
    #打印进度
    q = 'HQ' if isHQ else 'NQ'
    item_id = _item['item_id']
    item_name = _item['item_name']
    print(f'<剩余{time.strftime("%Hh%Mm%Ss",time.gmtime(time.time()-time_start)/item_progress*(item_count-item_progress))}s>[{item_progress}/{item_count}]{item_id}{q} - {item_name}')

    #分析本服成交数据
    count_in_time = 0   #本服成交量
    fre_in_time = 0    #本服成交次数
    i = 0
    list_world_his = []
    for item in _item['world_history']['entries']:
        if isHQ == item['hq']:
            if time_start-item['timestamp'] <= order_time:
                count_in_time+=item['quantity']
                fre_in_time+=1
            if i<order_world_his:
                list_world_his.append(item['pricePerUnit'])
            i+=1
    if len(list_world_his)==0:
        avg_list_world_his = 0
        std_list_world_his = 0
    else:
        avg_list_world_his = np.mean(list_world_his)    #本服成交价平均值
        std_list_world_his = np.std(list_world_his)     #本服成交价方差
    
    #分析本服挂售数据
    i = 0
    list_world_cur = []
    for item in _item['world_currently']['listings']:
        if isHQ == item['hq']:
            list_world_cur.append(item['pricePerUnit'])
            i+=1
            if i>=order_world_cur:break
    if len(list_world_cur)==0:
        avg_list_world_cur = 0
        std_list_world_cur = 0
    else:  
        avg_list_world_cur = np.mean(list_world_cur)    #本服挂售价平均值
        std_list_world_cur = np.std(list_world_cur)     #本服挂售价方差

    #分析全区挂售数据
    i = 0
    list_datacenter_cur = []
    for item in _item['datacenter_currently']['listings']:
        if isHQ == item['hq']:
            list_datacenter_cur.append(item['pricePerUnit'])
            i+=1
            if i>=order_datacenter_cur:break
    if len(list_datacenter_cur)==0:
        avg_list_datacenter_cur = 0
        std_list_datacenter_cur = 0
    else:
        avg_list_datacenter_cur = np.mean(list_datacenter_cur)  #全区挂售价平均值
        std_list_datacenter_cur = np.std(list_datacenter_cur)   #全区挂售价方差

    if avg_list_datacenter_cur==0:rate=0
    else:rate=avg_list_world_his/avg_list_datacenter_cur
    #写入结果
    with open(f_path,'a') as f:
        f.write(f'{item_id}{q},{item_name}{q},{avg_list_datacenter_cur},{std_list_datacenter_cur},{avg_list_world_his},{std_list_world_his},{avg_list_world_cur},{std_list_world_cur},{avg_list_world_cur-avg_list_world_his},{rate},{avg_list_world_his-avg_list_datacenter_cur},{fre_in_time},{count_in_time}')

#遍历物品，将NQ与HQ拆分为两种物品
for item_id in marketable_items:
    analyse(d['item_id'], True)
    analyse(d['item_id'], False)
    item_progress+=1
s.close()