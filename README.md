本项目由Claude、DeepSeek等大模型共同生成，本人小白，靠兴趣支撑了好多个通宵，仅提供思路、并整合、修改代码而成。
本项目是树莓派桌面云台机器人的交互系统（未完善动作指令），奈何本人毫无技术，难度太大，鏖战了好几个通宵才达到这个程度，后期会增加动作指令等相关功能。欢迎各位大神、专家完善本项目。

# BansrChat 技术架构

## 系统架构概览

BansrChat 由四个核心模块组成，形成完整的语音交互闭环：

1. **语音识别模块** (ASR) - 将用户语音转换为文本
2. **大语言模型模块** (LLM) - 处理文本并生成回复
3. **语音合成模块** (TTS) - 将文本回复转换为语音
4. **唤醒词检测模块** (可选) - 监听特定唤醒词

整体架构图：

```
+----------------+     +----------------+     +----------------+
|                |     |                |     |                |
|  语音输入设备   +---->+   语音识别     +---->+  大语言模型    |
|   (麦克风)      |     |    (ASR)      |     |    (LLM)      |
|                |     |                |     |                |
+----------------+     +----------------+     +----------------+
                                                      |
+----------------+     +----------------+             |
|                |     |                |             |
|  语音输出设备   +<----+   语音合成     +<------------+
|   (扬声器)      |     |    (TTS)      |
|                |     |                |
+----------------+     +----------------+

         ^
         |
+----------------+
|                |
|   唤醒词检测    |  (可选)
|    (Vosk)      |
|                |
+----------------+
```

## 核心模块详解

### 1. ASR.py - 语音识别模块

#### 主要功能：
- 通过麦克风捕获用户语音
- 实时将语音转换为文本
- 检测停顿和结束语，自动结束录音
- 集成大模型和TTS调用逻辑

#### 关键技术点：
- 使用讯飞语音听写WebSocket API
- 实现流式识别和WPGS（Word Partial Grammar Spotting）
- 静音检测和语音活动检测
- WebSocket连接管理和重连机制

### 2. spark_api.py - 大语言模型模块

#### 主要功能：
- 连接讯飞星火大模型API
- 处理用户文本输入
- 获取大模型生成的回复
- 管理对话历史上下文

#### 关键技术点：
- WebSocket连接和认证
- 流式接收模型回复
- 对话历史管理
- 错误处理和重试机制

### 3. tts_api.py - 语音合成模块

#### 主要功能：
- 将文本转换为自然语音
- 支持普通语音合成和超拟人语音合成
- 流式播放合成的语音

#### 关键技术点：
- 使用讯飞在线语音合成API
- 流式接收和播放音频数据
- 使用ffmpeg处理音频流
- 支持不同的语音合成参数调整

### 4. wake_up.py - 唤醒词检测模块

#### 主要功能：
- 离线监听特定唤醒词
- 唤醒词触发后启动完整对话流程

#### 关键技术点：
- 使用Vosk开源语音识别库
- 本地唤醒词检测，无需联网
- 低资源占用的持续监听机制

## 数据流和工作流程

### 标准对话流程

1. **语音输入阶段**
   - 麦克风捕获声音
   - 实时转发给语音识别服务
   - 实时显示识别结果
   - 检测到停顿后结束录音

2. **大模型处理阶段**
   - 将完整识别文本发送给星火大模型
   - 星火大模型根据对话历史和当前输入生成回复
   - 流式返回响应内容

3. **语音合成阶段**
   - 将大模型回复文本发送给语音合成服务
   - 流式接收合成的音频数据
   - 使用ffmpeg实时播放合成的语音

4. **循环阶段**
   - 语音播放完成后，回到第一步，等待新的语音输入
   - 或者检测到退出关键词，结束程序

### 唤醒模式工作流程

1. **等待唤醒阶段**
   - 持续监听环境声音
   - 使用Vosk进行本地语音识别
   - 匹配预设的唤醒词

2. **唤醒后流程**
   - 检测到唤醒词后播放欢迎语
   - 切换到标准对话流程
   - 对话结束后回到等待唤醒状态

## 性能优化策略

- **预连接机制**: 提前建立WebSocket连接，减少响应延迟
- **服务预初始化**: 程序启动时预先初始化各服务客户端
- **流式处理**: 全链路采用流式处理，实现低延迟交互
- **资源管理**: 适时释放不需要的连接和资源，优化内存使用
- **静音优化**: 在静音期间减少处理，降低CPU占用

## 扩展性设计

BansrChat 的模块化设计使其易于扩展：

- **支持其他语音识别引擎**: 可以替换ASR模块以使用其他厂商的API
- **支持其他大语言模型**: 修改spark_api.py可以集成其他LLM服务
- **自定义TTS引擎**: 可以替换或扩展TTS模块以使用其他语音合成服务
- **多模态支持**: 架构设计便于未来扩展到包含图像处理等多模态能力


# BansrChat 使用指南

## 运行模式

BansrChat 支持两种运行模式：

1. **直接对话模式** - 无需唤醒词，直接进行语音对话
2. **唤醒词模式** - 需要先说出唤醒词，才能开始对话

## 直接对话模式

### 启动方法

```bash
python ASR.py
```

### 交互流程

1. 程序启动后，会立即开始监听您的语音
2. 对着麦克风说话，系统会实时显示识别结果
3. 当您停止说话后（静音2秒），系统会自动结束录音
4. 星火大模型会处理您的问题并生成回复
5. 系统会通过语音合成播放回复内容
6. 回复播放完成后，系统会自动开始下一轮对话

### 结束对话

在任意对话中说出以下关键词之一可以结束程序：
- "停止"
- "退出"
- "结束程序"
- "关闭"
- "拜拜"
- "再见"

## 唤醒词模式

### 启动方法

```bash
python WakeUp.py
```

### 交互流程

1. 程序启动后，会等待您说出唤醒词
2. 默认唤醒词为：“一二三”（可在.env中自定义，建议选择常用词汇，Vosk的本地语言模型性能有限）
3. 当检测到唤醒词后，系统会播放欢迎语
4. 进入对话模式，操作方式与直接对话模式相同
5. 对话结束后（使用关键词退出或自然结束），系统会回到等待唤醒状态

## 常见问题解决

### 语音识别问题

如果您遇到语音识别不准确的问题：
- 确保使用较好的麦克风
- 尽量在安静的环境中使用
- 清晰地发音
- 调整 `.env` 文件中的识别相关参数

### 语音合成问题

如果语音合成效果不佳：
- 尝试调整 `.env` 文件中的 `TTS_VOICE`、`TTS_SPEED`、`TTS_VOLUME` 等参数
- 考虑启用超拟人语音合成模式（设置 `USE_SUPER_TTS=true`）

### 系统响应慢或无响应

如果系统响应速度慢：
- 检查网络连接
- 确认讯飞API密钥配置正确
- 查看控制台输出是否有错误信息

## 高级用法

### 自定义唤醒词

编辑 `.env` 文件中的 `WAKE_WORDS` 参数，多个唤醒词用逗号分隔。例如：

```
WAKE_WORDS=你好助手,小助手醒醒,开始对话
```

### 自定义大模型系统提示词

编辑 `.env` 文件中的 `SPARK_SYSTEM_PROMPT` 参数可以设置大模型的系统提示词，例如：

```
SPARK_SYSTEM_PROMPT=你是一个专业的助手，擅长回答简短清晰的问题
```

### 静音检测灵敏度调整

如果您发现系统过早结束录音或无法检测到您的语音输入完成，可以在代码中调整以下参数：

- `ASR.py` 文件中的 `SILENCE_THRESHOLD` 变量：调整静音检测的阈值
- `ASR.py` 文件中的 `MAX_SILENCE_TIME` 变量：调整静音持续多久后结束录音

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
git clone https://github.com/qiaogeno1/BansrChat.git
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

