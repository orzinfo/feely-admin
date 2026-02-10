#!/bin/bash

# 定义上游仓库名称和地址
REMOTE_NAME="soybean"
REMOTE_URL="https://github.com/soybeanjs/soybean-admin.git"
TARGET_DIR="web"
BRANCH="main"

# 检查是否在项目根目录
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' not found. Please run this script from the project root."
    exit 1
fi

# 检查 remote 是否存在，不存在则添加
if ! git remote | grep -q "^$REMOTE_NAME$"; then
    echo "Adding remote '$REMOTE_NAME'..."
    git remote add -f $REMOTE_NAME $REMOTE_URL
else
    echo "Remote '$REMOTE_NAME' already exists. Fetching updates..."
    git fetch $REMOTE_NAME
fi

echo "Updating '$TARGET_DIR' from '$REMOTE_NAME/$BRANCH'..."

# 使用 subtree pull 拉取更新
# --squash 选项可以将上游的多次提交合并为一次，保持主仓库历史整洁
git subtree pull --prefix=$TARGET_DIR $REMOTE_NAME $BRANCH --squash

if [ $? -eq 0 ]; then
    echo "Successfully updated '$TARGET_DIR'."
else
    echo "Failed to update '$TARGET_DIR'. Please check for conflicts."
fi
