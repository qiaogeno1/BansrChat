# BansrChat - 中文语音对话框架

BansrChat 是一个集成了语音识别、大型语言模型和语音合成的完整中文语音对话框架。该项目使用讯飞开放平台的相关 API，让您可以轻松构建自己的语音助手系统。

## 项目特点

- **全语音交互体验**：支持语音输入和语音输出，实现完全免手动操作的对话体验
- **实时语音识别**：使用讯飞语音听写 API 实现高准确率的实时语音识别
- **星火大模型集成**：内置讯飞星火大模型，提供智能对话能力
- **高质量语音合成**：支持讯飞普通语音合成和超拟人语音合成
- **热词唤醒功能**：支持通过 Vosk 实现自定义唤醒词，无需按键即可激活
- **全链路流式处理**：实现低延迟的自然交互体验
- **简单配置方式**：通过 .env 文件简单配置 API 密钥和各种参数

## 安装指南

### 前置要求

- Python 3.8 或更高版本
- [ffmpeg](https://ffmpeg.org/download.html) (用于音频处理)
- 讯飞开放平台账号及 API 密钥

### 步骤 1: 克隆仓库

bash
git clone https://github.com/yourusername/BansrChat.git
cd BansrChat


### 步骤 2: 安装依赖

bash
pip install -r requirements.txt


### 步骤 3: 配置 API 密钥（重要）

项目根目录中的 .env文件包含了所有配置参数的模板，但没有实际的 API 密钥。**使用前必须配置您自己的讯飞 API 密钥信息**：

1. 在讯飞开放平台 (https://www.xfyun.cn/) 注册并创建应用
2. 开通语音听写、在线语音合成和星火大模型能力
3. 获取应用的 APPID、API_KEY 和 API_SECRET
4. 编辑 `.env` 文件，填入您的密钥信息：


APPID=your_app_id
API_KEY=your_api_key
API_SECRET=your_api_secret


**注意：** 没有正确配置 API 密钥，程序将无法正常工作。

### 步骤 4: 下载 Vosk 模型 (可选，仅唤醒功能需要)

如果需要使用语音唤醒功能，请下载 Vosk 语音识别模型：

bash
# 创建模型目录
mkdir vosk-model-small-cn

# 下载并解压中文小型模型
wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
unzip vosk-model-small-cn-0.22.zip -d vosk-model-small-cn


## 使用方法

### ⚠️ 必要的前置步骤：配置 API 密钥

在使用 BansrChat 前，您必须先配置讯飞开放平台的 API 密钥：

1. 在讯飞开放平台 (https://www.xfyun.cn/) 注册并创建应用
2. 开通语音听写、在线语音合成和星火大模型能力
3. 获取应用的 APPID、API_KEY 和 API_SECRET
4. 编辑项目根目录中的 `.env` 文件，填入您获取的密钥

**详细说明请阅读：[API 密钥配置说明](docs/important-setup-note.md)**

### 运行模式

BansrChat 支持两种运行模式：

### 1. 直接启动语音对话 (按键启动模式)

bash
python ASR.py


在这个模式下，程序会立即开始监听您的语音输入。说话后停顿 2 秒会自动结束录音，系统将通过星火大模型给出回答并播放语音。

### 2. 使用语音唤醒 (热词唤醒模式)

bash
python WakeUp.py


在这个模式下，程序会等待您说出唤醒词（默认为"一二三"、"你好小知"等），听到唤醒词后才开始对话。

## 配置选项

您可以在.env文件中定制以下参数：

### 通用配置

APPID=your_app_id
API_KEY=your_api_key
API_SECRET=your_api_secret


### 语音识别配置

ASR_BASE_URL=wss://iat-api.xfyun.cn/v2/iat


### 大模型配置

SPARK_BASE_URL=wss://spark-api.xf-yun.com/v1.1/chat
SPARK_API_VERSION=lite
SPARK_SYSTEM_PROMPT=自定义系统提示词


### 普通语音合成配置

TTS_BASE_URL=wss://tts-api.xfyun.cn/v2/tts
TTS_VOICE=xiaoyan
TTS_SPEED=50
TTS_VOLUME=70
TTS_PITCH=50


### 超拟人语音合成配置

USE_SUPER_TTS=false
SUPER_TTS_BASE_URL=your_super_tts_url
SUPER_TTS_VOICE_ID=x4_lingxiaoli_oral
SUPER_TTS_FORMAT=wav
SUPER_TTS_SAMPLE_RATE=24000
SUPER_TTS_VOLUME=100
SUPER_TTS_SPEED=50
SUPER_TTS_CONVERT=0


### 唤醒配置

VOSK_MODEL_PATH=vosk-model-small-cn
WAKE_WORDS=一二三,你好小知,小智小智


## 项目结构


BansrChat/
├── ASR.py                # 语音识别和主程序
├── spark_api.py          # 星火大模型API模块
├── tts_api.py            # 语音合成模块
├── WakeWp.py             # 语音唤醒模块
├── requirements.txt      # 项目依赖
└── docs/                 # 文档目录
    ├── basic-usage.md           # 基本使用指南
    ├── technical-architecture.md # 技术架构
    ├── xfyun-integration.md     # 讯飞平台集成指南
    └── deployment-guide.md      # 部署指南


## 核心功能

### 1. 语音识别
使用讯飞实时语音识别，支持流式识别和动态修正，可实时显示识别结果。系统会自动检测停顿，在用户说完话后结束录音。

### 2. 大模型交互
集成讯飞星火大模型，支持上下文理解和自然语言处理。可以通过环境变量配置系统提示词，自定义助手的角色和行为。

### 3. 语音合成
支持多种发音人和语音参数调整，可以选择普通语音合成或超拟人语音合成，实现自然流畅的语音输出。

### 4. 语音唤醒
基于开源的 Vosk 引擎实现本地语音唤醒功能，支持自定义唤醒词，无需联网即可实现唤醒。

## 常见问题

### 如何设置唤醒词？
在.env文件中修改 WAKE_WORDS 参数，多个唤醒词用逗号分隔。

### 如何切换发音人？
在 .env 文件中修改 TTS_VOICE 参数，选择不同的发音人。常用选项有：
- xiaoyan: 小燕 (女声)
- aisjiuxu: 许久 (男声)
- x_lingxiaoli: 灵小丽 (女声)

### 如何结束对话？
在对话中说出以下关键词之一可以结束程序：
- "停止"
- "退出"
- "结束程序"
- "关闭"
- "拜拜"
- "再见"

## 其他资源

- [讯飞开放平台](https://www.xfyun.cn/)
- [Vosk语音识别](https://alphacephei.com/vosk/)
- [详细部署指南](docs/deployment-guide.md)
- [技术架构文档](docs/technical-architecture.md)

## 贡献

欢迎提交 Issues 和 Pull Requests 来帮助改进 BansrChat 项目。任何形式的贡献都将受到感谢！
