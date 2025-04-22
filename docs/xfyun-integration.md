# 讯飞开放平台集成指南

本文档介绍如何在 BansrChat 中正确配置和使用讯飞开放平台的相关服务。

## 创建讯飞开放平台账号

在开始使用 BansrChat 前，您需要：

1. 注册讯飞开放平台账号：https://www.xfyun.cn/
2. 完成实名认证
3. 创建应用并开通以下能力：
   - 语音听写
   - 在线语音合成
   - 星火大模型 (Spark)
   - [可选] 超拟人语音合成

## 获取 API 密钥

创建应用后，您需要获取以下信息并配置到 `.env` 文件中：

- APPID: 应用 ID
- API_KEY: 应用 API 密钥
- API_SECRET: 应用 API 密钥对应的密钥

在讯飞开放平台控制台，依次点击：应用管理 -> 我的应用 -> 选择您的应用 -> 接口认证信息，即可获取上述信息。

## 语音听写服务配置

语音听写服务默认使用中文普通话识别引擎。如果需要调整，可以在 `ASR.py` 文件中修改 `WsParam` 类的 `BusinessArgs` 参数：

```python
self.BusinessArgs = {
    "domain": "iat",          # 领域
    "language": "zh_cn",      # 语言，可选：zh_cn, en_us 等
    "accent": "mandarin",     # 方言，可选：mandarin, cantonese 等
    "vad_eos": 5000,          # 静音检测超时时间，单位为毫秒
    "dwa": "wpgs"             # 是否开启动态修正
}
```

## 星火大模型配置

BansrChat 默认使用讯飞星火认知大模型的 lite 版本。您可以在 `.env` 文件中调整以下参数：

```
SPARK_API_VERSION=lite  # 可选值: lite, standard, pro
```

如果您希望调整大模型的参数，可以在 `spark_api.py` 文件中修改 `_generate_payload` 方法：

```python
payload = {
    "header": {
        "app_id": self.APPID,
        "uid": uid
    },
    "parameter": {
        "chat": {
            "domain": self.SPARK_API_VERSION,
            "temperature": 0.7,  # 温度系数，控制输出的随机性
            "max_tokens": 1024   # 最大生成长度
        }
    },
    "payload": {
        "message": {
            "text": messages
        }
    }
}
```

## 语音合成服务配置

BansrChat 支持两种语音合成模式：普通语音合成和超拟人语音合成。

### 普通语音合成

在 `.env` 文件中配置以下参数：

```
TTS_VOICE=xiaoyan      # 发音人，可选值请参考讯飞文档
TTS_SPEED=50           # 语速，范围 0-100
TTS_VOLUME=70          # 音量，范围 0-100
TTS_PITCH=50           # 音高，范围 0-100
```

常用发音人列表：
- xiaoyan: 小燕 (女声)
- aisjiuxu: 许久 (男声)
- aisxping: 小萍 (女声)
- aisjinger: 小婧 (女声)
- aisbabyxu: 萌小新 (童声)
- x2_yifeng: 姚逸峰 (男声)
- x2_qianqian: 萱萱 (女声)
- x_yifeng: 姚逸峰精品 (男声)
- x_xiaoyan: 小燕精品 (女声)
- x_lingxiaoli: 灵小丽 (女声)
- x_lingxiaoxuan: 灵小璇 (女声)

### 超拟人语音合成

要使用超拟人语音合成，需要在讯飞开放平台上开通该服务，然后在 `.env` 文件中配置以下参数：

```
USE_SUPER_TTS=true
SUPER_TTS_BASE_URL=您的超拟人TTS服务地址
SUPER_TTS_VOICE_ID=x4_lingxiaoli_oral  # 超拟人发音人ID
SUPER_TTS_FORMAT=wav                    # 音频格式
SUPER_TTS_SAMPLE_RATE=24000             # 采样率
SUPER_TTS_VOLUME=100                    # 音量
SUPER_TTS_SPEED=50                      # 语速
```

常用超拟人发音人ID：
- x4_lingxiaoli_oral: 灵小丽口语化
- x4_lingxiaoxuan_em_v2: 灵小璇情感化第二版
- x4_lingxiaojun_oral: 灵小君口语化
- x4_lingxiaozhi_oral: 灵小智口语化
- x4_lingxiaoai_story: 灵小艾故事化

## WebSocket 连接参数

如果需要调整 WebSocket 连接参数，可以在 `.env` 文件中配置以下地址：

```
ASR_BASE_URL=wss://iat-api.xfyun.cn/v2/iat
TTS_BASE_URL=wss://tts-api.xfyun.cn/v2/tts
SPARK_BASE_URL=wss://spark-api.xf-yun.com/v1.1/chat
```

注意：除非讯飞开放平台官方通知更新，否则不建议修改这些地址。

## 常见问题

### 授权错误

如果出现 "认证失败" 或 "鉴权错误"，请检查：

1. APPID、API_KEY 和 API_SECRET 是否正确配置
2. 服务是否已在讯飞开放平台开通
3. 服务是否在可用期限内
4. 系统时间是否准确（鉴权依赖于时间戳）

### 余额不足

免费额度用完后，需要在讯飞开放平台充值或购买服务包。各服务的计费规则和余额可在控制台查看。

### 并发数限制

讯飞开放平台对不同服务有不同的并发数限制，如果超过限制可能会出现连接失败的情况。可以考虑：

1. 升级服务套餐增加并发数
2. 添加请求重试机制
3. 实现请求排队和流量控制

### 超时问题

如果出现请求超时，可以调整以下参数：

- 在 `spark_api.py` 中调整 `max_timeout` 参数
- 在 `tts_api.py` 中调整 `max_wait_time` 参数

## 关于讯飞星火认知大模型的版本

讯飞星火认知大模型有多个版本可供选择，不同版本的能力和定价不同：

- **Spark Lite**: 基础版大模型，适合简单对话和信息查询
- **Spark Standard**: 标准版大模型，具备更强的推理能力
- **Spark Pro**: 专业版大模型，具有最强的理解能力和生成能力

在开发和测试阶段，建议使用 Lite 版本以节省额度；在正式产品中，可以根据需求选择合适的版本。

要切换版本，只需在 `.env` 文件中修改 `SPARK_API_VERSION` 参数即可。