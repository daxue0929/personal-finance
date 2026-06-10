#!/bin/bash

# ========================================
# 前端部署脚本
# 用于构建和部署前端应用到服务器
# ========================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
DEPLOY_DIR="/opt/personal-finance/frontend"
BUILD_DIR="./dist"
NGINX_CONF_DIR="/etc/nginx/conf.d"
NGINX_CONF_FILE="personal-finance-frontend.conf"

# 打印带颜色的信息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以 root 权限运行
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 root 权限运行此脚本"
        print_info "提示：使用 sudo ./deploy.sh"
        exit 1
    fi
}

# 检查构建目录是否存在
check_build() {
    if [ ! -d "$BUILD_DIR" ]; then
        print_error "构建目录 $BUILD_DIR 不存在"
        print_info "请先运行 npm run build 构建项目"
        exit 1
    fi
}

# 创建部署目录
create_deploy_dir() {
    print_info "创建部署目录..."
    if [ ! -d "$DEPLOY_DIR" ]; then
        mkdir -p "$DEPLOY_DIR"
        print_info "目录 $DEPLOY_DIR 已创建"
    else
        print_info "目录 $DEPLOY_DIR 已存在"
    fi
}

# 复制构建文件
copy_files() {
    print_info "复制构建文件到部署目录..."
    rm -rf "$DEPLOY_DIR/dist"
    cp -r "$BUILD_DIR" "$DEPLOY_DIR/"
    print_info "文件复制完成"
}

# 创建 Nginx 配置文件
create_nginx_config() {
    print_info "创建 Nginx 配置文件..."
    
    # 检查配置文件是否已存在
    if [ -f "$NGINX_CONF_DIR/$NGINX_CONF_FILE" ]; then
        print_warn "配置文件已存在，备份旧配置..."
        # 备份旧配置文件（带时间戳）
        backup_file="$NGINX_CONF_DIR/$NGINX_CONF_FILE.bak.$(date +%Y%m%d_%H%M%S)"
        cp "$NGINX_CONF_DIR/$NGINX_CONF_FILE" "$backup_file"
        print_info "旧配置已备份到: $backup_file"
    fi
    
    cat > "$NGINX_CONF_DIR/$NGINX_CONF_FILE" <<EOF
server {
    listen 83;
    
    server_name wangxuedi.com www.wangxuedi.com;

    location / {
        root /opt/personal-finance/frontend/dist;
        index index.html index.htm;
        try_files \$uri \$uri/ /index.html;  # 适用于单页面应用
    }

    location /prod-api/ {
        add_header Cache-Control no-cache;
        proxy_pass http://127.0.0.1:5000/;
        client_max_body_size 25M;
        client_body_buffer_size 128k;
        fastcgi_intercept_errors on;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'Upgrade';
    }
}
EOF
    
    print_info "Nginx 配置文件已创建: $NGINX_CONF_DIR/$NGINX_CONF_FILE"
}

# 测试 Nginx 配置
test_nginx_config() {
    print_info "测试 Nginx 配置..."
    if nginx -t; then
        print_info "Nginx 配置测试通过"
    else
        print_error "Nginx 配置测试失败"
        exit 1
    fi
}

# 重载 Nginx
reload_nginx() {
    print_info "重载 Nginx 服务..."
    systemctl reload nginx
    print_info "Nginx 服务已重载"
}

# 显示完成信息
show_complete() {
    echo ""
    print_info "========================================"
    print_info "  前端部署完成！"
    print_info "========================================"
    echo ""
    print_info "访问地址：http://$(hostname -I | awk '{print $1}'):83"
    echo ""
    print_info "部署目录：$DEPLOY_DIR"
    print_info "Nginx 配置：$NGINX_CONF_DIR/$NGINX_CONF_FILE"
    echo ""
}

# 主函数
main() {
    echo ""
    print_info "========================================"
    print_info "  开始部署前端应用"
    print_info "========================================"
    echo ""
    
    check_root
    check_build
    create_deploy_dir
    copy_files
    create_nginx_config
    test_nginx_config
    reload_nginx
    show_complete
}

# 执行主函数
main