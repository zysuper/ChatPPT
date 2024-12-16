# 使用 Python 3.10 作为基础镜像构建环境
FROM python:3.10-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
	ffmpeg \
	&& rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 使用 Python 3.10 作为运行环境基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 从构建环境复制 Python 依赖
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# 安装运行时必需的系统依赖
RUN apt-get update && apt-get install -y \
	ffmpeg \
	&& rm -rf /var/lib/apt/lists/*

# 复制源代码
COPY src/ src/

# 创建输出目录
RUN mkdir -p outputs

# 设置环境变量
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 7860

# 设置启动命令
CMD ["python", "src/gradio_server.py"]
