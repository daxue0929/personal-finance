#!/bin/bash

# ========================================
# 前端部署脚本 - Nginx 配置更新
# 用于配置 Nginx 并部署前端应用
# ========================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
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
        proxy_pass http://127.0.0.1:5000/api/;
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
    print_info "前端目录：/opt/personal-finance/frontend/dist"
    print_info "Nginx 配置：$NGINX_CONF_DIR/$NGINX_CONF_FILE"
    echo ""
}

# 主函数
main() {
    echo ""
    print_info "========================================"
    print_info "  开始配置前端 Nginx"
    print_info "========================================"
    echo ""
    
    check_root
    create_nginx_config
    test_nginx_config
    reload_nginx
    show_complete
}

# 执行主函数
main
