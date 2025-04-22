# 部署指南

本文档提供了如何将 BansrChat 项目部署到不同环境中的详细说明。

## 基础环境要求

- Python 3.8 或更高版本
- 麦克风和扬声器设备
- 网络连接（用于调用讯飞API）
- ffmpeg 工具（语音播放依赖）

## 本地开发环境部署

### 步骤 1: 克隆仓库

```bash
git clone https://github.com/yourusername/BansrChat.git
cd BansrChat
```

### 步骤 2: 创建并激活虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 步骤 3: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 4: 安装 ffmpeg

#### Windows
1. 下载 ffmpeg: https://ffmpeg.org/download.html
2. 解压缩下载的文件
3. 将 ffmpeg 的 bin 目录添加到系统 PATH 环境变量

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Mac
```bash
brew install ffmpeg
```

### 步骤 5: 配置环境变量

复制 `.env.example` 文件并重命名为 `.env`，然后编辑该文件填入您的讯飞 API 密钥及其他配置。

### 步骤 6: 运行程序

```bash
# 直接语音对话模式
python ASR.py

# 或使用唤醒词模式
python wake_up.py
```

## 树莓派部署

### 步骤 1: 准备树莓派

1. 确保树莓派运行最新版本的 Raspberry Pi OS
2. 连接USB麦克风和音箱（或使用3.5mm音频输出）

### 步骤 2: 安装依赖

```bash
# 更新系统
sudo apt update
sudo apt upgrade

# 安装必要的库
sudo apt install python3-pip python3-venv ffmpeg portaudio19-dev libffi-dev libssl-dev

# 克隆仓库
git clone https://github.com/yourusername/BansrChat.git
cd BansrChat

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤 3: 配置音频设备

```bash
# 列出音频设备
arecord -l
aplay -l

# 编辑音频配置文件
sudo nano /etc/asound.conf
```

添加以下内容（根据您的设备ID调整）：

```
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:0,0"  # 根据aplay -l的输出调整
    }
    capture.pcm {
        type plug
        slave.pcm "hw:1,0"  # 根据arecord -l的输出调整
    }
}
```

### 步骤 4: 设置自启动（可选）

创建 systemd 服务以便开机自启动：

```bash
sudo nano /etc/systemd/system/BansrChat.service
```

添加以下内容：

```
[Unit]
Description=BansrChat Voice Assistant
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/BansrChat
ExecStart=/home/pi/BansrChat/venv/bin/python /home/pi/BansrChat/WakeUp.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl enable BansrChat.service
sudo systemctl start BansrChat.service
```

## Docker 部署

### 步骤 1: 创建 Dockerfile

在项目根目录创建 `Dockerfile`：

```dockerfile
FROM python:3.9-slim

# 安装 ffmpeg 和必要的依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建环境变量文件（需要在构建前准备好）
COPY .env .

# 暴露必要的端口（如果有需要）
# EXPOSE 8000

# 运行应用
CMD ["python", "ASR.py"]
```

### 步骤 2: 构建和运行 Docker 镜像

```bash
# 构建镜像
docker build -t bansrchat .

# 运行容器
docker run -it --device /dev/snd:/dev/snd bansrchat
```

注意：在 Docker 中使用音频设备需要特殊权限，上述命令将主机的声音设备映射到容器中。

## 性能优化建议

1. **提高语音识别精度**：
   - 使用高质量麦克风
   - 在安静环境中使用
   - 调整静音检测阈值

2. **减少网络延迟**：
   - 确保稳定的网络连接
   - 使用有线网络而非无线网络
   - 选择距离较近的讯飞服务器区域

3. **优化内存使用**：
   - 定期清理无用资源
   - 限制对话历史的长度
   - 使用更轻量级的 Vosk 模型（针对唤醒功能）

## 故障排除

### 音频设备问题

如果遇到音频设备问题：

```bash
# 查看可用的音频设备
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(p.get_device_info_by_index(i)) for i in range(p.get_device_count())]"
```

然后根据输出在代码中指定正确的设备索引：

```python
# 在 ASR.py 和 wake_up.py 中找到 p.open() 函数调用
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=0,  # 修改为正确的输入设备索引
    frames_per_buffer=CHUNK
)
```

### 权限问题

在 Linux 系统中，可能需要添加用户到 audio 组以访问音频设备：

```bash
sudo usermod -a -G audio $USER
# 需要注销并重新登录以使更改生效
```

### 其他常见问题

- **讯飞 API 连接失败**：检查网络连接和 API 密钥配置
- **语音识别不准确**：尝试调整麦克风位置或使用更高质量的麦克风
- **播放没有声音**：检查系统音量和默认音频设备设置
