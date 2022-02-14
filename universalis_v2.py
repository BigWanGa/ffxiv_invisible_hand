#!/usr/bin/python3
import json
import re
from urllib import response
import requests
import time
import os
import numpy as np
import openpyxl
import sys
import getopt

#----------配置部分----------
#调试配置
isDebug = False             #调试开关
debugCounts = 30            #限定查询条目数，仅开启调试时生效
isDebugLog = False          #调试日志开关，用于打印额外日志

#缓存配置
isClear = False             #重置缓存开关，也可以在运行脚本时使用参数激活此选项
isSkipNoName = False         #跳过没有缓存到中文名的道具，大概率是国服未上线道具，但也可能是网络原因。开启的意义是加速查询过程

#API相关
world_name = '白银乡'
datacenter_name = '莫古力'
url_now = 'https://universalis.app/api'
url_history = 'https://universalis.app/api/history'
url_marketable = 'https://universalis.app/api/marketable'
url_itemInfo = 'https://cafemaker.wakingsands.com/item/'
url_itemInfo_arg = '?columns=Name,StackSize'
block_version = ['6.0']                 #用于过滤国服未开放的版本道具

#分析参数
order_day = 30                          #统计多少天内的成交记录
order_time = order_day*24*3600          #将前一天数转换为秒数，后面计算时使用此变量
order_datacenter_cur = 4                #全区挂售价只看最低的前几
order_world_his = 5                     #本服成交价只看最近的前几，为-1时则使用按统计成交记录的范围
order_world_cur = 4                     #本服挂售价只看最低的前几

#输出与缓存路径
f_path = f'{world_name}.xlsx'
m_path = 'marketable.json'
n_path = 'itemName.json'
fail_path = 'fail_itemName.json'

#筛选配置
isfilter = False        #筛选开关
rate_min = 1.5          #利润率最小值
rate_max = 20           #利润率最大值
count_in_time_min = 15 #月成交次数最小值
p_world_his_max = 0.4   #本服成交价波动最大值
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
s=requests.session()

#封装一个带错误处理的数据获取方法
def urlGet(url):
    i = 3   #最多重试三次
    if isDebugLog: time_s = time.time()
    while i>=0:
        try:
            j = json.loads(s.get(url=url).content.decode())
            if isDebugLog: print(f'\n\t----服务器响应用时：{int((time.time() - time_s) * 1000)}ms')
            return j
        except:
            i-=1
    return ''

#筛选规则
def filter(rate, count_in_time, p_world_his):
    if rate < rate_min or rate > rate_max: return False
    if count_in_time < count_in_time_min: return False
    if p_world_his > p_world_his_max: return False
    return True

#进度条
def pro_bar(s, now, total):
    n_bar = 20
    l_bar = '_'
    c_bar = '='
    str_bar = ''
    for i in range(n_bar):
        if i/n_bar <= now/total:
            str_bar+=l_bar
        else:
            str_bar+=c_bar
    print(f'{s}:{str_bar} - {now}/{total}',end='\r')
    return

#命令行参数响应
argv = sys.argv[1:]
for arg in argv:
    if arg == '--clear':
        isClear = True          #响应'--clear'清理缓存选项
        print('选项：清理缓存')
    if arg == '--debug':
        isDebug = True          #响应'--debug'开启调试选项
        print('选项：调试模式')
    if arg == '--log':          #响应'--log'输出额外日志选项
        isDebugLog = True
        print('选项：开启额外日志输出')

#初始化：获取可交易物品列表并缓存到本地，类型为list
if not(isClear) and os.path.isfile(m_path):
    fm=open(m_path,"r")
    marketable_items=json.loads(fm.read())
    fm.close()
else:
    marketable_items=json.loads(s.get(url=url_marketable).content.decode())
    #检查道具版本，去除国服当前未进版的道具
    total = len(marketable_items)
    i = 0
    for itemid in marketable_items:
        time_s = time.time()
        if urlGet(f'https://xivapi.com/item/{itemid}?columns=GamePatch.Version')['GamePatch']['Version'] in block_version:
            marketable_items.remove(itemid)
        pro_bar(f'正在检查道具版本，耗时{int(1000 * (time.time() - time_s))}ms', i, total)
        i+=1
        if isDebug and i >= debugCounts: break
    s.close()
    print(f'道具版本检查完成，剔除了{total - len(marketable_items)}个国服未进版的道具')
    #道具版本检查完成，写入缓存
    fm=open(m_path,"w")
    fm.write(str(marketable_items))
    fm.close()

if len(marketable_items)!=0:
    print("可交易物品列表初始化完成，物品数："+str(len(marketable_items)))
else:
    print("可交易物品列表初始化失败，退出")
    exit()

#初始化：获取道具固有数据并缓存到本地，类型为dict
#固有数据包括：中文名称，堆叠数量
itemInfo = dict()
if not(isClear) and os.path.isfile(n_path):
    try:
        fn=open(n_path,'r')
        itemInfo = json.load(fn)
        fn.close()
        print(f'从缓存载入了{len(itemInfo)}个道具数据\n')
    except:
        print('读取道具中文名出错，已删除缓存，请重新运行本脚本\n')
        os.remove(n_path)
        exit()
else:
    list_fail = []
    if isDebug: i = 0       #若开启调查模式则统计查询次数
    total = len(marketable_items)
    for id in marketable_items:
        info = urlGet(f'{url_itemInfo}{id}{url_itemInfo_arg}')
        info_dict = dict()
        if info['StackSize'] == '':
            info_dict['StackSize'] = 0
        else:
            info_dict['StackSize'] = info['StackSize']
        info_dict['Name_cn'] = info['Name']
        if info['Name']!='':
            info_dict['Name_cn'] = info['Name']
        else:
            info_dict['Name_cn'] = ''
            list_fail.append(id)
        itemInfo[str(id)] = info_dict
        if isDebug: i+=1    #若开启调查模式则统计查询次数
        if isDebug and i >= debugCounts:break   #若开启调试模式则限制查询次数
        pro_bar('正在获取道具名称', i, total)
    if len(itemInfo)!=0:
        print(f'获取了{len(itemInfo)}/{total}个物品的中文名称，现在写入到缓存文件\n')
        with open(n_path,'w') as fn:
            json.dump(itemInfo, fn)
        if os.path.isfile(n_path):
            print('写入成功\n')
        else:
            print('写入失败，请检查权限或存储器剩余空间\n')
    if len(list_fail)!=0:
        print(f'以下id获取名称失败：\n{list_fail}，将写入日志{fail_path}\n')
        fn=open(fail_path,'w')
        fn.write(json.dumps(list_fail))
        fn.close()
        if os.path.isfile(fail_path):
            print('写入成功\n')
        else:
            print('写入失败，请检查权限或存储器剩余空间\n')

#初始化c：生成xlsx文件并写入首行
f_column = []
f_column.append('物品ID')
f_column.append('物品名称')
f_column.append('最大堆叠数量')
f_column.append('全区挂售价')
f_column.append('全区挂售价标准差')
f_column.append('本服成交价')
f_column.append('本服成交价标准差')
f_column.append('本服成交价波动')
f_column.append('本服挂售价')
f_column.append('本服挂售价标准差')
f_column.append('本服挂售价与成交价差值')
f_column.append('利润率')
f_column.append('单价差')
f_column.append('本服近一个月成交次数')
f_column.append('本服近一个月成交数量')
f_column.append('本服近一个月成交金额')

wb = openpyxl.Workbook()
ws=wb.active
ws.append(f_column)
#初始化csv文件完毕

#记录进度
item_count=len(marketable_items)
item_progress=1
time_start=time.time()

#分析物品的函数
def analyse(id, name, data_cur, data_his, data_dc_cur, isHQ):

    if isDebugLog: time_a = time.time()
    #初始化道具后缀
    q = 'HQ' if isHQ else 'NQ'
    
    #分析本服成交数据
    count_in_time = 0   #本服成交量
    fre_in_time = 0     #本服成交次数
    money_in_time = 0   #本服成交金额
    i = 0
    list_world_his = []
    for item in data_his['entries']:
        if isHQ == item['hq']:
            if time_start-item['timestamp'] <= order_time:
                count_in_time+=item['quantity']
                fre_in_time+=1
                money_in_time+=item['pricePerUnit'] * item['quantity']
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
    #若开启输出过滤，则只输出过滤后的内容
    if(isfilter):
        if not(filter(rate, count_in_time, p_world_his)):
            return

    #杂项数据生成
    name_link = f'=HYPERLINK("https://universalis.app/market/{id}","{name}{q}")'
    result = [str(id)+q,name_link,itemInfo[str(itemid)]['StackSize'],avg_list_datacenter_cur,std_list_datacenter_cur,avg_list_world_his,std_list_world_his,p_world_his,avg_list_world_cur,std_list_world_cur,avg_list_world_cur-avg_list_world_his,rate,avg_list_world_his-avg_list_datacenter_cur,fre_in_time,count_in_time,money_in_time]
    if isDebugLog:  print(f'\n\t----数据分析用时：{int((time.time() - time_a) * 1000)}ms')

    #写入结果
    if isDebugLog: time_s = time.time()
    wb.active.append(result)
    if isDebugLog:  print(f'\n\t----写入文件用时：{int((time.time() - time_s) * 1000)}ms')

#开始获取
for itemid in marketable_items:
    #获取道具名称
    if isDebugLog: time_f = time.time()
    item_name = itemInfo[str(itemid)]['Name_cn']
    if isDebugLog: print(f'\n\t----名称查找用时：{int((time.time() - time_f) * 1000)}ms')
    if item_name == '':continue
    
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
#写入文件
if isDebugLog: time_r = time.time()
wb.save(f_path)
if isDebugLog: print(f'\n\t----写入结果用时：{int((time.time() - time_r) * 1000)}ms')

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
        2. 修复对道具名称查询的容错问题
    2022/01/31:
        1. 改用openpyxl写入Excel，以实现道具名称列写入universalis的超链接
        2. 增加近一月内的成交金额列
        3. 增加导出表格时的筛选
        4. 增加对道具中文名的缓存
        5. 初步添加对缓存读取出错的清理缓存机制
    2022/02/01:
        1. 增加对网络响应耗时的输出
    2022/02/02:
        1. 分析发现变慢是因为之前错误地重复打开文件，修正了这一错误，并将每分析一次写入一次文件改为最后写入文件
    2022/02/14:
        1. 修复累计本服近一月成交额时没计算数量的bug
        2. 输出表格中添加道具的可堆叠性列

后续方向：
    1. 组合交易数量进行平均价的计算
    2. 对可堆叠和不可堆叠的道具分别优化计算方式
    3. 逐步确定筛选条件，最终做到每天在网页上刷新两次当日推荐商品top50
    4. 添加对名称获取失败的道具重新查询名称的功能
    5. 将写入文件与错误处理及提示封装为独立函数
    6. 进一步完善需要的命令行参数功能，例如参数指定调试次数
    7. 完善缓存读取出错时的应对机制，加入对缓存文件完整性检查、缓存文件写入进度检查、缓存文件更新必要性判断等

笔记：
    1. 测试表明：
        a. 若不使用单一会话，获取一次ffxiv的回报要1.2s；使用单一会话时只需0.4s
        b. 若不指明要查询的数据列，拉取较多数据会让耗时增加近一倍
    2. 踩坑：json存储字典的key会把int存为string
'''
