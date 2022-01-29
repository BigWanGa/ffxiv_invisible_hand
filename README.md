# ffxiv_invisible_hand
## 主脚本
- universalis_v2.py 
  - 目前只有这个稳定可用，关于数据分析的迭代也是在这个脚本里进行。有网络通信的容错，对物品列表有本地缓存、不用每次运行都从云端拉取
  - 配置在脚本开头修改
                  
## 其他 
- universalis_pull.py
  - 将universalis中的数据全部拉到本地，没有做网络通信的容错，一次连接错误就会失败。没有做流式写入，内存需求超过2G
  - 应该不再维护，一方面需要存储的数据量太大，另一方面数据时效性很短，也没必要为了改进分析算法而一次性拉取全部数据
- universalis_analyse.py
  - 对前者拉回的json全部加载到内存中进行分析，需要进行流式读取的优化（https://pypi.org/project/ijson/）
