# BansrChat 环境搭建详细指南

本文档提供了 BansrChat 项目的详细环境搭建步骤，帮助您从零开始配置所需的一切。

## 讯飞开放平台账号配置

### 1. 注册讯飞开放平台账号

1. 访问讯飞开放平台官网：https://www.xfyun.cn/
2. 点击右上角的"注册"按钮
3. 按照提示完成账号注册流程
4. 登录后进入控制台

### 2. 实名认证

1. 在控制台页面，找到"实名认证"选项
2. 根据指引完成个人或企业实名认证
3. 等待审核通过（通常在1-2个工作日内）

### 3. 创建应用

1. 在左侧菜单选择"应用管理" -> "创建新应用"
2. 填写应用名称（如"BansrChat"）和应用描述
3. 选择适当的应用类型
4. 点击"创建"按钮

### 4. 开通能力

在创建的应用中，需要开通以下能力：

#### 语音听写（必须）：
1. 在应用详情页，点击"语音听写"
2. 阅读并同意服务条款
3. 点击"免费开通"按钮

#### 在线语音合成（必须）：
1. 点击"语音合成"
2. 阅读并同意服务条款
3. 点击"免费开通"按钮

#### 星火大模型（必须）：
1. 点击"星火认知大模型"
2. 阅读并同意服务条款
3. 点击"免费开通"按钮

#### 超拟人语音合成（可选）：
1. 点击"超拟人语音合成"
2. 阅读并同意服务条款
3. 申请开通服务

### 5. 获取密钥信息

1. 在应用详情页，点击"接口认证信息"标签
2. 记录以下信息：
   - APPID
   - API KEY
   - API SECRET

## Python 环境配置

### Windows 系统

1. 下载并安装 Python：
   - 访问 https://www.python.org/downloads/
   - 下载 Python 3.8 或更高版本
   - 运行安装程序，确保勾选"Add Python to PATH"选项

2. 安装 ffmpeg：
   - 访问 https://ffmpeg.org/download.html
   - 下载 Windows 版本的 ffmpeg
   - 解压到一个固定位置（例如 C:\ffmpeg）
   - 将 ffmpeg 的 bin 目录（如 C:\ffmpeg\bin）添加到系统环境变量 PATH 中

3. 克隆项目：
   ```bash
   git clone https://github.com/yourusername/BansrChat.git
   cd BansrChat
   ```

4. 创建虚拟环境：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

5. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

### Linux 系统 (Ubuntu/Debian)

1. 安装 Python 和必要工具：
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv git
   ```

2. 安装 ffmpeg 和音频相关依赖：
   ```bash
   sudo apt install -y ffmpeg portaudio19-dev
   ```

3. 克隆项目：
   ```bash
   git clone https://github.com/yourusername/BansrChat.git
   cd BansrChat
   ```

4. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

### MacOS 系统

1. 安装 Homebrew（如果尚未安装）：
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. 安装 Python 和 ffmpeg：
   ```bash
   brew install python ffmpeg portaudio
   ```

3. 克隆项目：
   ```bash
   git clone https://github.com/yourusername/BansrChat.git
   cd BansrChat
   ```

4. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 配置环境变量（关键步骤）

1. 项目根目录中已包含 `.env` 文件，其中包含了所有配置项的结构但没有实际的 API 密钥：

2. **必须编辑 `.env` 文件，填入您的讯飞 API 密钥信息：**
   ```
   APPID=您的讯飞APPID
   API_KEY=您的讯飞API_KEY
   API_SECRET=您的讯飞API_SECRET
   ```

3. 这一步是最关键的配置步骤，如果没有正确配置 API 密钥，程序将无法连接讯飞服务。

4. 根据需要调整其他配置参数（如语音合成发音人、模型版本等）

## 设置语音唤醒模型（可选）

如果您需要使用语音唤醒功能，请下载 Vosk 语音识别模型：

1. 创建模型目录：
   ```bash
   mkdir vosk-model-small-cn
   ```

2. 下载中文小型模型：
   - 访问 https://alphacephei.com/vosk/models
   - 下载 "vosk-model-small-cn-0.22" 模型
   - 解压到 vosk-model-small-cn 目录

   或者使用命令行：
   ```bash
   wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
   unzip vosk-model-small-cn-0.22.zip -d vosk-model-small-cn
   ```

## 测试安装

### 测试语音对话功能：

```bash
python ASR.py
```

如果一切配置正确，程序应该启动并等待您的语音输入。

### 测试唤醒功能：

```bash
python WakeUp.py
```

程序应该启动并等待您说出唤醒词（如"一二三"）。

## 常见问题解决

### PyAudio 安装问题

如果 PyAudio 安装失败，可以尝试：

#### Windows：
```bash
pip install pipwin
pipwin install pyaudio
```

#### Linux：
```bash
sudo apt install python3-pyaudio
```

#### MacOS：
```bash
brew install portaudio
pip install --global-option='build_ext' --global-option='-I/usr/local/include' --global-option='-L/usr/local/lib' pyaudio
```

### ffmpeg 相关问题

确保 ffmpeg 已正确安装且可在命令行中访问：

```bash
ffmpeg -version
```

如果命令不可用，请检查是否已将 ffmpeg 添加到系统 PATH 中。

### 麦克风权限问题

确保您的应用有权限访问麦克风：

- **Windows**：检查隐私设置中的麦克风权限
- **MacOS**：在系统偏好设置 -> 安全性与隐私 -> 麦克风中授予权限
- **Linux**：确保用户在 audio 组中，运行 `sudo usermod -a -G audio $USER`，然后重新登录

### 网络连接问题

确保您的计算机能够连接到讯飞开放平台服务器：

```bash
ping spark-api.xf-yun.com
```

## 下一步

成功设置环境后，请参考以下文档继续了解 BansrChat：

- [基本使用指南](basic-usage.md)
- [技术架构文档](technical-architecture.md)
- [讯飞平台集成指南](xfyun-integration.md)
- [部署指南](deployment-guide.md)
