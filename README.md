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
│   ├── .env         # 环境配置文件
│   ├── Dockerfile   # Docker 构建文件
│   ├── docker-compose.yml # Docker Compose 配置
│   ├── requirements.txt   # Python 依赖
│   └── deploy.sh    # 部署脚本
├── frontend/        # 前端项目
│   ├── src/         # 源代码
│   │   ├── api/     # API 请求封装
│   │   ├── components/ # 公共组件
│   │   ├── router/  # 路由配置
│   │   └── views/   # 页面视图
│   ├── dist/        # 构建产物
│   ├── .env.development # 开发环境配置
│   ├── .env.production  # 生产环境配置
│   ├── package.json # 前端依赖配置
│   ├── vite.config.js # Vite 配置
│   └── deploy.sh    # 前端部署脚本
├── sql/             # SQL 脚本目录
│   ├── program/     # 存储过程脚本
│   └── struct/      # 数据库结构脚本
```

#### 软件架构

本项目采用前后端分离架构：

**后端服务**
- 语言：Python 3.10+
- 框架：Flask
- 任务调度：APScheduler
- 数据库：MySQL

**前端项目**
- 语言：Vue 3 + JavaScript
- 构建工具：Vite 5.0
- UI框架：Element Plus
- 路由：Vue Router

**模块划分**
- 数据爬虫服务：负责从各大财经网站抓取基金数据和指数数据
- Web API 服务：提供 RESTful API 接口
- 前端应用：提供用户交互界面，包括基金管理、购买者管理、任务管理等功能

#### 环境搭建

**后端服务**
1. 安装依赖
```bash
cd data-crawler
pip install -r requirements.txt
```

2. 配置数据库连接
- 修改 `.env` 文件配置 MySQL 连接信息

3. 启动服务
```bash
python -m app.main --port 5001
```

**前端项目**
1. 安装依赖
```bash
cd frontend
npm install
```

2. 开发环境启动
```bash
npm run dev
```

3. 生产环境构建
```bash
npm run build
```
构建完之后, 连带着 dist 目录下的文件, 都需要提交到版本控制中,然后在服务器git pull 下来就更新了前端代码.

**服务访问**
- 前端：http://localhost:3000
- 后端API：http://localhost:5001

#### 设计思路
