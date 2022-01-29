#!/usr/bin/python3
import json
from urllib import response
import requests
import time
import os
import numpy as np

#----------配置部分----------
#调试配置
isDebug = False             #调试开关
debugCounts = 100           #限定查询条目数，仅开启调试时生效

#区服ID与API网址
world_name = '白银乡'
datacenter_name = '莫古力'
url_now = 'https://universalis.app/api'
url_history = 'https://universalis.app/api/history'

#分析参数
order_day = 30                          #统计多少天内的成交记录
order_time = order_day*24*3600          #将前一天数转换为秒数，后面计算时使用此变量
order_datacenter_cur = 4                #全区挂售价只看最低的前几
order_world_his = 5                     #本服成交价只看最近的前几，为-1时则使用按统计成交记录的范围
order_world_cur = 4                     #本服挂售价只看最低的前几

#----------配置结束----------

'''
思路：
1.获取可交易物品id list
2.遍历list：
    1.查询白银乡当前价格与历史价格
    2.查询猪区当前价格与历史价格
    3.分析：
        1.每个道具分析一次
        2.对全区挂售价取最低的N个计算平均值，记录标准差
        3.对本区成交价取最近的M个计算平均值，记录标准差
        4.对本区挂售价取最低的X个计算平均值，记录标准差，记录挂售价平均值与成交价平均值的差值
        5.对于挂售价，若有单个数据是其余数据的10倍，则剔除
        6.对于成交价，若由单个数据是其余数据的1/10倍，则剔除
        7.以本区成交价平均值与全区挂售价平均值对比得出利润率、单价差
        8.NQ与HQ作为两种道具对待
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

#初始化csv文件
f_path = f'{world_name}.csv'

c1 = '物品ID'
c2 = '物品名称'
c3 = '全区挂售价'
c4 = '全区挂售价标准差'
c5 = '本服成交价'
c6 = '本服成交价标准差'
c6_p = '本服成交价波动'
c7 = '本服挂售价'
c8 = '本服挂售价标准差'
c9 = '本服挂售价与成交价差值'
c10 = '利润率'
c11 = '单价差'
c12 = '本服近一个月成交次数'
c13 = '本服近一个月成交数量'

f_column = f'{c1},{c2},{c3},{c4},{c5},{c6},{c6_p},{c7},{c8},{c9},{c10},{c11},{c12},{c13}\n'
with open(f_path,'w') as f:
    f.write(f_column)
#初始化csv文件完毕

#记录进度
item_count=len(marketable_items)
item_progress=1
time_start=time.time()

#封装一个带错误处理的数据获取方法
def urlGet(url):
    i = 3   #最多重试三次
    while i>=0:
        try:
            return json.loads(s.get(url=url).content.decode())
        except:
            i-=1
    return ''

#分析物品的函数
def analyse(id, name, data_cur, data_his, data_dc_cur, isHQ):
    #初始化道具后缀
    q = 'HQ' if isHQ else 'NQ'

    #分析本服成交数据
    count_in_time = 0   #本服成交量
    fre_in_time = 0     #本服成交次数
    i = 0
    list_world_his = []
    for item in data_his['entries']:
        if isHQ == item['hq']:
            if time_start-item['timestamp'] <= order_time:
                count_in_time+=item['quantity']
                fre_in_time+=1
                if order_world_his==-1:
                    list_world_his.append(item['pricePerUnit'])
            if order_world_his!=-1:    
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
    for item in data_cur['listings']:
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
    for item in data_dc_cur['listings']:
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
    else:rate=avg_list_world_his/avg_list_datacenter_cur-1
    if avg_list_world_his==0:p_world_his=0
    else:p_world_his=std_list_world_his/avg_list_world_his

    #若无数据则不写入
    if avg_list_world_cur==0 and avg_list_world_his==0 and avg_list_datacenter_cur==0: return

    name_link = f'=HYPERLINK("https://universalis.app/market/{id},"{name}{q}")'
    #写入结果
    with open(f_path,'a') as f:
        f.write(f'{id}{q},{name_link},{avg_list_datacenter_cur},{std_list_datacenter_cur},{avg_list_world_his},{std_list_world_his},{p_world_his},{avg_list_world_cur},{std_list_world_cur},{avg_list_world_cur-avg_list_world_his},{rate},{avg_list_world_his-avg_list_datacenter_cur},{fre_in_time},{count_in_time}\n')

#开始获取
for itemid in marketable_items:
    #获取道具名称
    item_name = urlGet(f'https://cafemaker.wakingsands.com/item/{itemid}?columns=Name')['Name']
    #打印进度
    print("<剩余"+str(time.strftime("%Hh%Mm%Ss",time.gmtime((time.time()-time_start)/item_progress*(item_count-item_progress))))+">["+str(item_progress)+"/"+str(item_count)+"]"+str(itemid)+" - "+str(item_name))
    item_progress+=1

    #使用封装过的容错方法以避免一次出错整个中断
    data_cur = urlGet(f'{url_now}/{world_name}/{itemid}')
    data_his = urlGet(f'{url_history}/{world_name}/{itemid}')
    data_dc_cur = urlGet(f'{url_now}/{datacenter_name}/{itemid}')
    #若有获取失败则跳过此物品
    if data_cur=='' or data_his=='' or data_dc_cur=='':
        print(f'{itemid} - {item_name}读取失败\n')
        continue 

    #将NQ与HQ拆分为两种物品，调用分析函数
    analyse(itemid, item_name, data_cur, data_his, data_dc_cur, True)
    analyse(itemid, item_name, data_cur, data_his, data_dc_cur, False)

    #调试用：限制查询个数
    if isDebug:
        debugCounts-=1
        if debugCounts<=0:break
#结束，关闭会话
s.close()

'''
更新记录：
    2022/01/28:
        1. 将数据分析逻辑独立成一个方法
        2. 引入numpy库以计算方差，并添加方差/均值比作为波动值
        3. 将NQ与HQ作为两个不同的道具进行处理，并为ID与道具名添加NQ/HQ后缀
        4. 写入文件时使用with处理错误
        5. 添加调试开关
        6. 缓存可交易物品列表，运行时优先从本地读取
        7. 将经过时间累积改为剩余时间估算
    2022/01/29:
        1. 增加方法urlGet以防止resquests.get()出错（最多重试三次），出错时跳过这个物品
        2. 道具名称列写入universalis的超链接

后续方向：
    1. 组合交易数量进行平均价的计算
    2. 对可堆叠和不可堆叠的道具分别优化计算方式
'''