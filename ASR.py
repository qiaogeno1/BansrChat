#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 语音助手主程序：集成语音识别、大模型对话和语音合成
# 参考讯飞开放平台官方文档
# 语音听写: https://www.xfyun.cn/doc/asr/voicedictation/API.html
# 星火大模型: https://www.xfyun.cn/doc/spark/Web.html
# 语音合成: https://www.xfyun.cn/doc/tts/online_tts/API.html

import websocket
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import os
import pyaudio
import dotenv
import array
import sys

# 导入星火大模型模块
from spark_api import SparkAPI
# 导入语音合成模块
from tts_api import TTSApi

# 加载环境变量
dotenv.load_dotenv()
dotenv.load_dotenv(override=True) 
# 全局常量
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后帧的标识

# 全局变量
all_results = []  # 保存所有接收到的识别结果
current_combined_result = ""  # 当前累积的完整识别结果
continue_chat = True  # 控制是否继续对话的标志
ws_param = None  # WebSocket参数对象
asr_preconnected_ws = None  # 预连接的ASR WebSocket对象
# 添加以下全局变量，用于存储预初始化的服务
spark_global = None  # 全局Spark模型实例
tts_global = None    # 全局TTS实例
all_results = []  # 保存所有接收到的识别结果
current_combined_result = ""  # 当前累积的完整识别结果
continue_chat = True  # 控制是否继续对话的标志
ws_param = None  # WebSocket参数对象
asr_preconnected_ws = None  # 预连接的ASR WebSocket对象
spark_global = None  # 全局Spark模型实例
tts_global = None    # 全局TTS实例
asr_paused = False   # 控制ASR是否暂停
def preconnect_asr():
    """预连接到ASR服务器但不发送音频"""
    global ws_param, asr_preconnected_ws
    print("预连接ASR服务器...")
    ws_param = WsParam()
    ws_url = ws_param.create_url()
    
    # 创建WebSocketApp对象，使用不同的回调
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=lambda ws, msg: on_message(ws, msg),
        on_error=lambda ws, err: on_error(ws, err),
        on_close=lambda ws, code, reason: on_preconnect_close(ws, code, reason),
        on_open=on_preconnect_open
    )
    
    # 保存预连接对象
    asr_preconnected_ws = ws
    
    # 在后台线程运行连接
    def run_ws():
        try:
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        except Exception as e:
            print(f"预连接异常: {e}")
    
    thread.start_new_thread(run_ws, ())

def on_preconnect_open(ws):
    """预连接建立时的处理"""
    print("ASR预连接已建立，等待输入...")
    # 不发送音频数据，保持连接

def on_preconnect_close(ws, close_status_code, close_reason):
    """预连接关闭时的处理"""
    global asr_preconnected_ws
    print(f"ASR预连接关闭: {close_status_code}-{close_reason}")
    asr_preconnected_ws = None

def init_services():
    """预先初始化服务连接"""
    global spark_global, tts_global
    
    print("正在预初始化AI服务...")
    
    # 预初始化Spark
    try:
        from spark_api import SparkAPI
        spark_global = SparkAPI(auto_connect=True)  # 需要添加auto_connect参数支持
        print("星火大模型预初始化成功")
    except Exception as e:
        print(f"星火大模型预初始化失败: {e}")
        
    # 预初始化TTS
    try:
        from tts_api import TTSApi
        tts_global = TTSApi()
        tts_global.prepare_connection()  # 需要添加此方法
        print("TTS服务预初始化成功")
    except Exception as e:
        print(f"TTS服务预初始化失败: {e}")
def is_silent(audio_data, threshold):
    """
    检测音频是否为静音，不使用numpy
    :param audio_data: 音频数据
    :param threshold: 静音阈值
    :return: 是否为静音
    """
    # 将字节数据转换为short数组
    fmt = 'h' * (len(audio_data) // 2)  # 'h'表示short类型
    shorts = array.array('h', audio_data)
    
    # 计算音量 - 使用简单的最大绝对值
    max_volume = 0
    for sample in shorts:
        abs_sample = abs(sample)
        if abs_sample > max_volume:
            max_volume = abs_sample
    
    # 判断是否为静音
    return max_volume < threshold


def get_final_recognition_result(results_list): # 文字识别方法
    """
    根据所有识别结果，生成最终的纯文本识别结果
    :param results_list: 识别结果列表
    :return: 纯文本识别结果
    """
    if not results_list:
        return ""
        
    # 重新整理结果，分为已完成的句子和当前进行的句子
    final_sentence_results = []  # 已经结束的句子
    current_sentence_results = []  # 当前正在处理的句子
    
    # 将结果分为已结束句子和当前处理句子
    for result in results_list:
        if result.get("is_sentence_end", False):
            if current_sentence_results:
                # 当前句子有内容，合并后添加到已结束句子
                current_text = "".join([r["text"] for r in current_sentence_results])
                final_sentence_results.append(current_text)
                current_sentence_results = []
            
            # 添加结束句子
            final_sentence_results.append(result["text"])
        else:
            # 添加到当前处理句子
            current_sentence_results.append(result)
    
    # 构建最终显示结果
    final_result = ""
    
    # 添加已结束的句子
    if final_sentence_results:
        final_result += "".join(final_sentence_results)
    
    # 添加当前处理的句子（如果有）
    if current_sentence_results:
        # 非最终结果
        non_final_results = [r for r in current_sentence_results if not r.get("is_final", True)]
        if non_final_results:
            # 使用最新的非最终结果
            final_result += non_final_results[-1]["text"]
    
    return final_result


class WsParam(object):
    """
    讯飞开放平台WebAPI参数类
    """
    def __init__(self):
        # 从环境变量获取讯飞API参数
        self.APPID = os.getenv("APPID")
        self.API_KEY = os.getenv("API_KEY")
        self.API_SECRET = os.getenv("API_SECRET")
        self.ASR_URL = os.getenv("ASR_BASE_URL")
        
        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        
        # 业务参数(business)，更多参数可参考接口文档
        # 注意：只使用最基本的必要参数，避免使用可能导致错误的参数
        self.BusinessArgs = {
            "domain": "iat",  # 领域
            "language": "zh_cn",  # 语言
            "accent": "mandarin",  # 方言
            "vad_eos": 5000,  # 结束时间
            "dwa": "wpgs"  # 是否开启降噪
        }
        
    def create_url(self):
        """
        生成WebSocket鉴权URL
        """
        url = self.ASR_URL
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 生成RFC1123格式的时间戳
        signature_origin = f"host: ws-api.xfyun.cn\n"
        signature_origin += f"date: {date}\n"
        signature_origin += "GET /v2/iat HTTP/1.1"
        
        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            self.API_SECRET.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode()
        authorization_origin = f'api_key="{self.API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode()).decode()
        
        # 拼接鉴权参数
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        
        # 拼接URL
        url = url + '?' + urlencode(v)
        return url


def on_message(ws, message):
    """
    收到websocket消息的处理
    """
    global all_results, current_combined_result, continue_chat
    try:
        message_json = json.loads(message)
        
        # 解析结果
        if message_json["code"] != 0:
            print(f"错误码: {message_json['code']}, 错误信息: {message_json['message']}")
            return
        
        # 判断是否有结果
        if "data" not in message_json:
            return
            
        if "result" not in message_json["data"]:
            return
            
        # 检查是否有ws字段（识别结果）
        if "ws" not in message_json["data"]["result"]:
            return
        
        data = message_json["data"]["result"]["ws"]
        
        # 解析结果
        current_text = ""
        for i in data:
            if "cw" in i:
                for w in i["cw"]:
                    if "w" in w:
                        current_text += w["w"]
        
        # 忽略空结果
        if current_text.strip():
            # 判断是否是最终结果
            is_final = message_json["data"].get("status") == 2
            
            # 判断当前识别类型
            result_type = message_json["data"].get("result", {}).get("pgs")
            
            # 根据不同情况处理结果
            if is_final:
                # 这是最终结果，将其添加到最终结果列表
                # 如果是单个标点符号，可能需要特殊处理
                is_punctuation_only = all(char in "，。！？,.!?" for char in current_text)
                
                if is_punctuation_only and len(all_results) > 0:
                    # 如果只是标点符号且有前面的结果，将其附加到最后一个结果
                    for i in range(len(all_results) - 1, -1, -1):
                        if all_results[i].get("is_sentence_end", False) == False:
                            all_results[i]["text"] += current_text
                            all_results[i]["is_sentence_end"] = True
                            break
                else:
                    # 添加为新的最终结果
                    all_results.append({
                        "text": current_text,
                        "is_final": True,
                        "is_sentence_end": True  # 标记句子结束
                    })
                    
                print(f"最终识别片段: {current_text}")
            else:
                # 非最终结果处理
                
                if result_type == "rpl":
                    # 替换类型：需要替换前面临时结果的最后一个
                    # 找到最后一个未最终确认的结果进行替换
                    found = False
                    for i in range(len(all_results) - 1, -1, -1):
                        if all_results[i].get("is_final", True) == False:
                            all_results[i]["text"] = current_text
                            found = True
                            break
                    
                    # 如果没有找到可替换的，添加为新结果
                    if not found:
                        all_results.append({
                            "text": current_text,
                            "is_final": False,
                            "is_sentence_end": False
                        })
                elif result_type == "apd":
                    # 追加类型：直接添加新结果
                    all_results.append({
                        "text": current_text,
                        "is_final": False,
                        "is_sentence_end": False
                    })
                else:
                    # 无明确类型：也作为新结果添加
                    all_results.append({
                        "text": current_text,
                        "is_final": False,
                        "is_sentence_end": False
                    })
                    
                print(f"实时识别片段: {current_text}")
            
            # 重新构建完整结果
            # 策略：对全部结果按添加顺序拼接
            final_sentence_results = []  # 已经结束的句子
            current_sentence_results = []  # 当前正在处理的句子
            
            # 将结果分为已结束句子和当前处理句子
            for result in all_results:
                if result.get("is_sentence_end", False):
                    if current_sentence_results:
                        # 当前句子有内容，合并后添加到已结束句子
                        current_text = "".join([r["text"] for r in current_sentence_results])
                        final_sentence_results.append(current_text)
                        current_sentence_results = []
                    
                    # 添加结束句子
                    final_sentence_results.append(result["text"])
                else:
                    # 添加到当前处理句子
                    current_sentence_results.append(result)
            
            # 构建最终显示结果
            current_combined_result = ""
            
            # 添加已结束的句子
            if final_sentence_results:
                current_combined_result += "".join(final_sentence_results)
            
            # 添加当前处理的句子（如果有）
            if current_sentence_results:
                # 只保留最新的非最终结果
                non_final_results = [r for r in current_sentence_results if not r.get("is_final", True)]
                if non_final_results:
                    # 使用最新的非最终结果
                    current_combined_result += non_final_results[-1]["text"]
            
            # 显示当前累积的识别结果
            print(f"实时完整内容: {current_combined_result}")
            print("----------------------------")
            
            # 检查停止关键词
            stop_keywords = ["停止", "退出", "结束程序", "关闭", "拜拜", "再见"]
            if current_combined_result:
                for keyword in stop_keywords:
                    if keyword in current_combined_result:
                        print(f"\n检测到停止关键词: '{keyword}'，准备结束程序...")
                        continue_chat = False
                        
                        # 发送最后一帧来结束当前会话
                        try:
                            d = {
                                "data": {
                                    "status": STATUS_LAST_FRAME,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(b'').decode(),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                        except:
                            pass
                        
                        # 关闭WebSocket连接
                        ws.close()
                        return
            
    except Exception as e:
        print(f"处理消息时发生错误: {e}")
        import traceback
        print(traceback.format_exc())


def on_error(ws, error):
    """
    收到websocket错误的处理
    """
    print(f"### 错误: {error}")


def on_close(ws, close_status_code, close_reason):
    """
    websocket关闭的处理
    """
    print(f"### 连接关闭，状态码: {close_status_code}, 原因: {close_reason} ###")


def on_open(ws):
    """
    连接建立的处理
    """
    global ws_param
    
    print("### 连接已建立 ###")
    
    def run(*args):
        """
        发送音频数据的线程
        """
        global all_results, continue_chat, current_combined_result, spark_global, tts_global
        all_results = []  # 清空结果列表
        current_combined_result = "" # 清空当前累积结果
        # 使用预初始化的服务或创建新实例
        spark_model = spark_global if spark_global else None
        llm_called = False # 标记是否已调用LL

        
        status = STATUS_FIRST_FRAME  # 音频的状态信息
        
        # 音频参数
        CHUNK = 1280  # 每一帧的音频大小
        FORMAT = pyaudio.paInt16  # 16位深度，范围-32768至32767
        CHANNELS = 1  # 单声道
        RATE = 16000  # 16000采样频率
        SILENCE_THRESHOLD = 500  # 静音检测阈值
        MAX_SILENCE_TIME = 2  # 最大静音时间（秒）
        INITIAL_WAIT_TIME = 5  # 等待用户开始说话的最大时间（秒）
        
        # 创建音频对象
        p = pyaudio.PyAudio()
        
        # 打开麦克风
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print("* 录音中... (请在5秒内开始说话)")
        
        silence_frames = 0  # 记录静音帧数
        max_silence_frames = int(RATE / CHUNK * MAX_SILENCE_TIME)  # 最大静音帧数
        initial_wait_frames = int(RATE / CHUNK * INITIAL_WAIT_TIME)  # 初始等待最大帧数
        has_speech = False  # 标记是否检测到语音
        initial_silence_frames = 0  # 记录初始静音帧数
        
        try:
            for i in range(0, int(RATE * 60 / CHUNK)):  # 最大录音时长60秒
                # 读取音频数据
                try:
                    buf = stream.read(CHUNK, exception_on_overflow=False)
                except Exception as e:
                    print(f"读取音频流时出错: {e}")
                    continue
                
                # 判断是否为静音
                is_silence = is_silent(buf, SILENCE_THRESHOLD)
                
                # 检查是否超过初始等待时间
                if not has_speech:
                    if is_silence:
                        initial_silence_frames += 1
                        if initial_silence_frames % 10 == 0:  # 每10帧输出一次
                            remaining = INITIAL_WAIT_TIME - (initial_silence_frames * CHUNK / RATE)
                            print(f"等待用户开始说话: 还剩 {remaining:.1f} 秒")
                        
                        if initial_silence_frames >= initial_wait_frames:
                            print("未检测到语音输入，自动关闭会话...")
                            continue_chat = False
                            ws.close()
                            break
                    else:
                        # 检测到用户开始说话
                        has_speech = True
                        print("检测到语音输入，开始录音...")
                        # 预先创建 SparkAPI 实例
                        if spark_model is None and spark_global is not None:
                            spark_model = spark_global
                            print("使用预初始化的星火大模型...")
                        elif spark_model is None:
                            print("预先初始化星火大模型...")
                            try:
                                spark_model = SparkAPI()
                                print("星火大模型初始化成功。")
                            except Exception as e:
                                print(f"预先初始化星火大模型失败: {e}")
                                spark_model = None 
                
                # 如果已经检测到语音，则按正常的录音处理逻辑
                if has_speech:
                    # 如果检测到声音，重置静音计数
                    if not is_silence:
                        silence_frames = 0
                    # 只有在检测到语音后才开始计算静音时间
                    else:
                        silence_frames += 1
                        if silence_frames % 10 == 0: # 每10帧输出一次
                            print(f"检测到停止说话: {silence_frames}/{max_silence_frames} 帧")
                        
                        if silence_frames >= max_silence_frames:
                            # 检测到持续静音，发送最后一帧并立即调用LLM
                            print("检测到持续静音，发送最后一帧并准备调用大模型...")
                            d = {
                                "data": {
                                    "status": STATUS_LAST_FRAME,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(b'').decode(),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                            # 短暂等待，让on_message处理可能到来的最后消息
                            time.sleep(0.2) 
                            # 打印录音结束和最终文本 (重要：将这部分放在调用大模型之前)
                            print("* 录音结束")
                            final_text = get_final_recognition_result(all_results) # 使用处理函数获取完整结果
                            
                            if final_text.strip():
                                print(f"最终确认文本: {final_text}")
                            else:
                                print("没有识别到有效内容")
                            
                            # 检查停止关键词
                            stop_keywords = ["停止", "退出", "结束程序", "关闭", "拜拜", "再见"]
                            for keyword in stop_keywords:
                                if keyword in final_text:
                                    print(f"\n检测到停止关键词: '{keyword}'，准备结束程序...")
                                    continue_chat = False
                                    ws.close()
                                    return
                                
                            # 使用当前累积的结果调用LLM
                            if final_text.strip() and spark_model:
                                print(f"\n使用最终识别结果: {final_text}\n")
                                try:
                                    # 设置asr_paused标志
                                    asr_paused = True
                                    
                                    # 使用全局TTS实例，如果可用
                                    if tts_global is not None and spark_model.tts_api is None:
                                        spark_model.tts_api = tts_global
                                        spark_model.tts_initialized = True
                                        print("使用预初始化的TTS服务...")
                                    
                                    # 调用大模型 (不使用回调参数)
                                    response = spark_model.chat(final_text)
                                    
                                    # TTS播放完成后在这里重置标志
                                    print("TTS播放完成，准备恢复语音识别...")
                                    asr_paused = False
                                    
                                    llm_called = True # 标记已调用
                                    ws.close()
                                    print("ASR WebSocket连接已主动关闭")
                                except Exception as e:
                                    print(f"\n调用星火大模型时发生错误: {e}")
                                    # 确保出错时重置暂停标志
                                    asr_paused = False
                            elif not spark_model:
                                 print("\n星火大模型未成功初始化，无法获取回复。")
                            else:
                                print("\n没有有效的实时识别内容。")

                            break # 结束录音循环
                
                # 判断音频的状态
                if i == 0:
                    # 第一帧音频
                    status = STATUS_FIRST_FRAME
                elif i == int(RATE * 60 / CHUNK) - 1:
                    # 最后一帧音频
                    status = STATUS_LAST_FRAME
                else:
                    # 中间帧音频
                    status = STATUS_CONTINUE_FRAME
                
                # 第一帧发送业务和公共参数
                if status == STATUS_FIRST_FRAME:
                    d = {
                        "common": ws_param.CommonArgs,
                        "business": ws_param.BusinessArgs,
                        "data": {
                            "status": STATUS_FIRST_FRAME,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode(),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))

                # 中间帧只发送音频
                elif status == STATUS_CONTINUE_FRAME:
                    d = {
                        "data": {
                            "status": STATUS_CONTINUE_FRAME,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode(),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    # 保持稳定的发送节奏，不要太快也不要太慢
                    # time.sleep(0.05) # 注意：这里的sleep可能不需要或可以缩短
                # 最后一帧 (由于达到最大时长)
                elif status == STATUS_LAST_FRAME:
                    print("达到最大录音时长，发送最后一帧并准备调用大模型...")
                    d = {
                        "data": {
                            "status": STATUS_LAST_FRAME,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(b'').decode(),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    # 短暂等待
                    time.sleep(0.2) 
                    
                    # 使用当前累积的结果调用LLM
                    final_text = get_final_recognition_result(all_results)  # 使用处理函数获取完整结果
                    
                    # 检查停止关键词
                    stop_keywords = ["停止", "退出", "结束程序", "关闭", "拜拜", "再见"]
                    for keyword in stop_keywords:
                        if keyword in final_text:
                            print(f"\n检测到停止关键词: '{keyword}'，准备结束程序...")
                            continue_chat = False
                            ws.close()
                            return
                    
                    if final_text.strip() and spark_model:
                        print(f"\n使用最终识别结果: {final_text}\n")
                        try:
                            # 设置asr_paused标志
                            asr_paused = True
                            
                            # 使用全局TTS实例，如果可用
                            if tts_global is not None and spark_model.tts_api is None:
                                spark_model.tts_api = tts_global
                                spark_model.tts_initialized = True
                                print("使用预初始化的TTS服务...")
                            
                            # 调用大模型 (不使用回调参数)
                            response = spark_model.chat(final_text)
                            
                            # TTS播放完成后在这里重置标志
                            print("TTS播放完成，准备恢复语音识别...")
                            asr_paused = False
                            
                            llm_called = True # 标记已调用
                            ws.close()
                            print("ASR WebSocket连接已主动关闭")
                        except Exception as e:
                            print(f"\n调用星火大模型时发生错误: {e}")
                            # 确保出错时重置暂停标志
                            asr_paused = False
                    elif not spark_model:
                         print("\n星火大模型未成功初始化，无法获取回复。")
                    else:
                         print("\n没有有效的实时识别内容。")
                         
                    break # 结束录音循环
        
        except KeyboardInterrupt:
            # 用户手动结束
            print("用户中断录音")
        except Exception as e:
            print(f"发送音频时发生错误: {e}")
        
        finally:
            # 关闭音频流
            try:
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception as e:
                print(f"关闭音频流时出错: {e}")
    
    # 启动线程
    thread.start_new_thread(run, ())


def voice_chat():
    """
    进行语音对话
    :return: 是否继续对话的标志
    """
    global asr_preconnected_ws, ws_param, all_results, current_combined_result, spark_global, tts_global, continue_chat, asr_paused
    
    # 检查是否有预连接可用
    if asr_preconnected_ws and asr_preconnected_ws.sock and asr_preconnected_ws.sock.connected:
        print("使用预连接的ASR通道...")
        ws = asr_preconnected_ws
        # 替换回调函数为实际处理函数
        ws.on_message = on_message
        ws.on_close = on_close
        ws.on_open = on_open  # 确保on_open会启动录音线程
        # 需要重新发送业务参数（根据讯飞协议）
        d = {
            "common": ws_param.CommonArgs,
            "business": ws_param.BusinessArgs,
            "data": {
                "status": STATUS_FIRST_FRAME,
                "format": "audio/L16;rate=16000",
                "audio": "",  # 实际数据在录音线程发送
                "encoding": "raw"
            }
        }
        ws.send(json.dumps(d))
    else:
        # 正常建立新连接
        ws_param = WsParam()
        ws_url = ws_param.create_url()
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
    
    # 在on_open回调中设置一个闭包，允许访问ws对象
    def on_open_wrapper(original_on_open):
        def wrapper(ws):
            global all_results, continue_chat, current_combined_result, spark_global, tts_global, asr_paused
            
            print("### 连接已建立 ###")
            
            def run(*args):
                """
                发送音频数据的线程
                """
                global all_results, continue_chat, current_combined_result, spark_global, tts_global, asr_paused
                all_results = []  # 清空结果列表
                current_combined_result = "" # 清空当前累积结果
                
                # 使用预初始化的服务或创建新实例
                spark_model = spark_global if spark_global else None
                llm_called = False # 标记是否已调用LLM
                
                status = STATUS_FIRST_FRAME  # 音频的状态信息
                
                # 音频参数
                CHUNK = 1280  # 每一帧的音频大小
                FORMAT = pyaudio.paInt16  # 16位深度，范围-32768至32767
                CHANNELS = 1  # 单声道
                RATE = 16000  # 16000采样频率
                SILENCE_THRESHOLD = 300  # 静音检测阈值
                MAX_SILENCE_TIME = 2  # 最大静音时间（秒）
                INITIAL_WAIT_TIME = 5  # 等待用户开始说话的最大时间（秒）
                
                # 创建音频对象
                p = pyaudio.PyAudio()
                
                # 打开麦克风
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                print("* 录音中... (请在5秒内开始说话)")
                
                silence_frames = 0  # 记录静音帧数
                max_silence_frames = int(RATE / CHUNK * MAX_SILENCE_TIME)  # 最大静音帧数
                initial_wait_frames = int(RATE / CHUNK * INITIAL_WAIT_TIME)  # 初始等待最大帧数
                has_speech = False  # 标记是否检测到语音
                initial_silence_frames = 0  # 记录初始静音帧数
                
                try:
                    for i in range(0, int(RATE * 60 / CHUNK)):  # 最大录音时长60秒
                        # 读取音频数据
                        try:
                            buf = stream.read(CHUNK, exception_on_overflow=False)
                        except Exception as e:
                            print(f"读取音频流时出错: {e}")
                            continue
                        
                        # 判断是否为静音
                        is_silence = is_silent(buf, SILENCE_THRESHOLD)
                        
                        # 检查是否超过初始等待时间
                        if not has_speech:
                            if is_silence:
                                initial_silence_frames += 1
                                if initial_silence_frames % 10 == 0:  # 每10帧输出一次
                                    remaining = INITIAL_WAIT_TIME - (initial_silence_frames * CHUNK / RATE)
                                    print(f"等待用户开始说话: 还剩 {remaining:.1f} 秒")
                                
                                if initial_silence_frames >= initial_wait_frames:
                                    print("未检测到语音输入，自动关闭会话...")
                                    continue_chat = False
                                    ws.close()
                                    break
                            else:
                                # 检测到用户开始说话
                                has_speech = True
                                print("检测到语音输入，开始录音...")
                                # 预先创建 SparkAPI 实例
                                if spark_model is None and spark_global is not None:
                                    spark_model = spark_global
                                    print("使用预初始化的星火大模型...")
                                elif spark_model is None:
                                    print("预先初始化星火大模型...")
                                    try:
                                        spark_model = SparkAPI()
                                        print("星火大模型初始化成功。")
                                    except Exception as e:
                                        print(f"预先初始化星火大模型失败: {e}")
                                        spark_model = None 
                        
                        # 如果已经检测到语音，则按正常的录音处理逻辑
                        if has_speech:
                            # 如果检测到声音，重置静音计数
                            if not is_silence:
                                silence_frames = 0
                            # 只有在检测到语音后才开始计算静音时间
                            else:
                                silence_frames += 1
                                if silence_frames % 10 == 0: # 每10帧输出一次
                                    print(f"检测到停止说话: {silence_frames}/{max_silence_frames} 帧")
                                
                                if silence_frames >= max_silence_frames:
                                    # 检测到持续静音，发送最后一帧并立即调用LLM
                                    print("检测到持续静音，发送最后一帧并准备调用大模型...")
                                    d = {
                                        "data": {
                                            "status": STATUS_LAST_FRAME,
                                            "format": "audio/L16;rate=16000",
                                            "audio": base64.b64encode(b'').decode(),
                                            "encoding": "raw"
                                        }
                                    }
                                    ws.send(json.dumps(d))
                                    # 短暂等待，让on_message处理可能到来的最后消息
                                    time.sleep(0.2) 
                                    # 打印录音结束和最终文本
                                    print("* 录音结束")
                                    final_text = get_final_recognition_result(all_results)
                                    
                                    if final_text.strip():
                                        print(f"最终确认文本: {final_text}")
                                    else:
                                        print("没有识别到有效内容")
                                    
                                    # 检查停止关键词
                                    stop_keywords = ["停止", "退出", "结束程序", "关闭", "拜拜", "再见"]
                                    for keyword in stop_keywords:
                                        if keyword in final_text:
                                            print(f"\n检测到停止关键词: '{keyword}'，准备结束程序...")
                                            continue_chat = False
                                            ws.close()
                                            return
                                    
                                    # 使用当前累积的结果调用LLM
                                    if final_text.strip() and spark_model:
                                        print(f"\n使用最终识别结果: {final_text}\n")
                                        try:
                                            # 设置 ASR 暂停标志
                                            asr_paused = True
                                            
                                            # 调用星火大模型 (不使用回调参数)
                                            response = spark_model.chat(final_text)
                                            llm_called = True # 标记已调用
                                            
                                            # TTS 播放完成后在这里重置标志
                                            # SparkAPI 的 chat 方法会等待 TTS 播放完成
                                            print("TTS 播放完成，准备恢复语音识别...")
                                            asr_paused = False
                                            
                                            ws.close()
                                            print("ASR WebSocket连接已主动关闭")
                                        except Exception as e:
                                            print(f"\n调用星火大模型时发生错误: {e}")
                                            # 确保出错时也重置暂停标志
                                            asr_paused = False
                                    elif not spark_model:
                                         print("\n星火大模型未成功初始化，无法获取回复。")
                                    else:
                                         print("\n没有有效的实时识别内容。")
                                    
                                    break # 结束录音循环
                        
                        # 判断音频的状态
                        if i == 0:
                            # 第一帧音频
                            status = STATUS_FIRST_FRAME
                        elif i == int(RATE * 60 / CHUNK) - 1:
                            # 最后一帧音频
                            status = STATUS_LAST_FRAME
                        else:
                            # 中间帧音频
                            status = STATUS_CONTINUE_FRAME
                        
                        # 第一帧发送业务和公共参数
                        if status == STATUS_FIRST_FRAME:
                            d = {
                                "common": ws_param.CommonArgs,
                                "business": ws_param.BusinessArgs,
                                "data": {
                                    "status": STATUS_FIRST_FRAME,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(buf).decode(),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                        
                        # 中间帧只发送音频
                        elif status == STATUS_CONTINUE_FRAME:
                            d = {
                                "data": {
                                    "status": STATUS_CONTINUE_FRAME,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(buf).decode(),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                            
                        # 最后一帧 (由于达到最大时长)
                        elif status == STATUS_LAST_FRAME:
                            print("达到最大录音时长，发送最后一帧并准备调用大模型...")
                            d = {
                                "data": {
                                    "status": STATUS_LAST_FRAME,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(b'').decode(),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                            # 短暂等待
                            time.sleep(0.2) 
                            
                            # 使用当前累积的结果调用LLM
                            final_text = get_final_recognition_result(all_results)
                            
                            # 检查停止关键词
                            stop_keywords = ["停止", "退出", "结束程序", "关闭", "拜拜", "再见"]
                            for keyword in stop_keywords:
                                if keyword in final_text:
                                    print(f"\n检测到停止关键词: '{keyword}'，准备结束程序...")
                                    continue_chat = False
                                    ws.close()
                                    return
                            
                            if final_text.strip() and spark_model:
                                print(f"\n使用最终识别结果: {final_text}\n")
                                try:
                                    # 设置asr_paused标志
                                    asr_paused = True
                                    
                                    # 定义TTS完成回调
                                    def on_tts_complete():
                                        global asr_paused
                                        print("TTS播放完成，准备恢复语音识别...")
                                        asr_paused = False
                                    
                                    # 使用全局TTS实例，如果可用
                                    if tts_global is not None and spark_model.tts_api is None:
                                        spark_model.tts_api = tts_global
                                        spark_model.tts_initialized = True
                                        print("使用预初始化的TTS服务...")
                                    
                                    # 带回调调用大模型
                                    response = spark_model.chat(
                                        final_text, 
                                        on_tts_complete=on_tts_complete
                                    )
                                    llm_called = True # 标记已调用
                                    ws.close()
                                    print("ASR WebSocket连接已主动关闭")
                                except Exception as e:
                                    print(f"\n调用星火大模型时发生错误: {e}")
                                    # 确保出错时重置暂停标志
                                    asr_paused = False
                            elif not spark_model:
                                 print("\n星火大模型未成功初始化，无法获取回复。")
                            else:
                                 print("\n没有有效的实时识别内容。")
                                 
                            break # 结束录音循环
                
                except KeyboardInterrupt:
                    # 用户手动结束
                    print("用户中断录音")
                except Exception as e:
                    print(f"发送音频时发生错误: {e}")
                
                finally:
                    # 关闭音频流
                    try:
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                    except Exception as e:
                        print(f"关闭音频流时出错: {e}")
            
            # 启动线程
            thread.start_new_thread(run, ())
            
        return wrapper
    
    # 替换原始on_open回调
    original_on_open = on_open
    ws.on_open = on_open_wrapper(original_on_open)
    
    # 运行WebSocket
    try:
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    except Exception as e:
        print(f"连接错误: {e}")
    
    # 清理预连接标记
    asr_preconnected_ws = None
    return continue_chat  # 返回是否继续对话的标志


def main():
    """
    主程序入口
    """
    global continue_chat, ws_param, spark_global, tts_global, asr_paused
    
    # 初始化变量
    ws_param = WsParam()
    asr_paused = False  # 新增：控制ASR是否暂停
    
    # 启动服务预初始化（在单独线程中进行，避免阻塞主流程）
    import _thread as thread
    thread.start_new_thread(init_services, ())
    
    print("==== 讯飞语音识别 + 星火大模型交互系统 + 语音合成 ====")
    print("请对着麦克风说话，系统会识别您的语音并通过星火大模型给出回复")
    print("说话后停顿2秒会自动结束录音，大模型将对您的内容进行回复")
  
    # 主循环
continue_chat = True

while continue_chat:
    try:
        # 检查是否处于暂停状态
        if asr_paused:
            print("正在等待TTS播放完成...")
            time.sleep(0.5)  # 短暂等待
            continue  # 跳过本次循环
            
        # 预连接ASR
        thread.start_new_thread(preconnect_asr, ())
        
        # 进行语音对话
        continue_chat = voice_chat()
        
        # 检查是否需要退出
        if not continue_chat:
            print("\n收到停止指令，程序正在退出...")
            break
            
    except KeyboardInterrupt:
        print("\n收到键盘中断，程序正在退出...")
        continue_chat = False
        break
    
    print("\n程序已退出")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"\n程序发生致命错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)