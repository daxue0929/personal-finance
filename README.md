# personal-finance

#### 介绍

本项目是一个基于个人财务管理系统，用于记录个人的财务信息和交易记录。

#### 软件目录

```
personal-finance/
├── data-crawler/    # 基金数据爬虫服务
│   └── app/         # 应用程序代码
│       ├── parser/  # 数据解析模块
│       ├── scheduler/ # 任务调度模块
│       ├── storage/   # 数据存储模块
│       ├── task/      # 定时任务模块
│       ├── utils/     # 工具函数模块
│       └── web/       # Web API 模块
├── sql/             # SQL 脚本目录
│   ├── program/     # 存储过程脚本
│   └── struct/      # 数据库结构脚本
```

#### 软件架构

本项目的软件架构如下：

- 数据库：MySQL
- 存储过程：存储过程脚本目录下的 SQL 脚本
- 数据库初始化脚本：备份init/下的 SQL 脚本

#### 环境搭建

1. 配置mcp环境
```bash
pip install uv

.trae\mcp.json 中配置 MySQL 服务器的连接信息
```


1. xxxx
2. xxxx

#### 设计思路
