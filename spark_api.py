#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 星火大模型API调用模块
# 参考讯飞开放平台星火大模型官方文档
# https://www.xfyun.cn/doc/spark/Web.html

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
import uuid
import dotenv

# 导入TTS API
from tts_api import TTSApi

# 加载环境变量
dotenv.load_dotenv()
dotenv.load_dotenv(override=True) 
class SparkAPI:
    """
    星火大模型API调用
    """
    def __init__(self, auto_connect=False):
        # 从环境变量获取星火API参数
        self.APPID = os.getenv("APPID")
        self.API_KEY = os.getenv("API_KEY")
        self.API_SECRET = os.getenv("API_SECRET")
        self.SPARK_URL = os.getenv("SPARK_BASE_URL")
        self.SPARK_API_VERSION = os.getenv("SPARK_API_VERSION", "lite")
        
        # 获取系统提示词
        self.SYSTEM_PROMPT = os.getenv("SPARK_SYSTEM_PROMPT", "")
        
        # WebSocket连接
        self.ws = None
        # 当前回复文本
        self.current_response = ""
        # 完成标志
        self.done = False
        # 对话历史
        self.conversation_history = []
        
        # TTS相关属性
        self.tts_api = None
        self.tts_initialized = False
        self.first_token_received = False
        # 连接状态
        self.is_connected = False
        self.connection_ready = False
        self.connection_url = None
        
        # 如果需要自动连接
        if auto_connect:
            self.prepare_connection()
    def prepare_connection(self):
        """
        预先准备WebSocket连接但不发送数据
        """
        # 生成URL并存储以备后用
        self.connection_url = self.create_url()
        self.connection_ready = True
        return self.connection_url
    def create_url(self):
        """
        生成WebSocket鉴权URL
        """
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = f"host: spark-api.xf-yun.com\ndate: {date}\nGET /v1.1/chat HTTP/1.1"

        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            self.API_SECRET.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode()

        authorization_origin = f'api_key="{self.API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode()).decode()

        # 将鉴权信息添加到URL
        v = {
            "authorization": authorization,
            "date": date,
            "host": "spark-api.xf-yun.com"
        }
        url = self.SPARK_URL + '?' + urlencode(v)
        return url

    def _generate_payload(self, query):
        """
        生成请求消息体
        """
        # 构建消息历史
        messages = []
        
        # 添加系统提示词
        if self.SYSTEM_PROMPT:
            messages.append({
                "role": "system",
                "content": self.SYSTEM_PROMPT
            })
        
        # 添加历史对话
        for msg in self.conversation_history:
            messages.append(msg)
            
        # 添加当前用户问题
        messages.append({
            "role": "user",
            "content": query
        })
        
        # 生成32字符以内的uid
        uid = str(uuid.uuid4())[:32]
        
        payload = {
            "header": {
                "app_id": self.APPID,
                "uid": uid
            },
            "parameter": {
                "chat": {
                    "domain": self.SPARK_API_VERSION,
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
            },
            "payload": {
                "message": {
                    "text": messages
                }
            }
        }
        return payload

    def on_message(self, ws, message):
        """
        收到WebSocket消息的处理
        """
        data = json.loads(message)
        code = data["header"]["code"]
        
        if code != 0:
            print(f"星火大模型返回错误: {data}")
            self.done = True
            return
            
        choices = data["payload"]["choices"]
        status = choices["status"]
        content = choices["text"][0]["content"]
        
        # 收到第一个token时初始化TTS API
        if not self.first_token_received and content.strip():
            self.first_token_received = True
            # 在另一个线程中初始化TTS API，以免阻塞当前处理
            thread.start_new_thread(self._initialize_tts_api, ())
            print("检测到首个字符，开始初始化TTS API...")
        
        # 累积回复文本
        self.current_response += content
        print(content, end="", flush=True)
        
        # 若已结束，打印完整回复
        if status == 2:
            self.done = True
            
            # 将助手回复加入对话历史
            self.conversation_history.append({
                "role": "assistant",
                "content": self.current_response
            })

    def _initialize_tts_api(self):
        """
        初始化TTS API
        """
        try:
            if not self.tts_initialized:
                self.tts_api = TTSApi()
                self.tts_initialized = True
                print("TTS API 初始化成功，等待大模型完成回复...")
        except Exception as e:
            print(f"初始化TTS API失败: {e}")
            self.tts_initialized = False

    def on_error(self, ws, error):
        """
        WebSocket报错处理
        """
        print(f"星火大模型连接错误: {error}")
        self.done = True

    def on_close(self, ws, close_status_code, close_reason):
        """
        WebSocket关闭处理
        """
        print(f"星火大模型连接关闭: {close_status_code}, {close_reason}")
        # 如果连接异常关闭且没有完成对话，标记为已完成并设置一个错误消息
        if not self.done:
            print("连接异常关闭，但对话未完成")
            if not self.current_response:
                self.current_response = "星火大模型连接意外关闭，无法获取完整回复。"
            self.done = True

    def on_open(self, ws):
        """
        WebSocket连接建立处理
        """
        def run(*args):
            """
            WebSocket运行线程
            """
            # 发送请求
            try:
                ws.send(json.dumps(self.payload))
            except Exception as e:
                print(f"发送请求失败: {e}")
                self.done = True
        thread.start_new_thread(run, ())

    def reset_conversation(self):
        """
        重置对话历史
        """
        self.conversation_history = []
        print("对话历史已重置")

    def chat(self, query, on_tts_complete=None):
        """
        发送消息并获取回复
        :param query: 用户问题
        :param on_tts_complete: TTS播放完成时的回调函数
        :return: 大模型的回复文本
        """
        # 重置状态
        self.current_response = ""
        self.done = False
        self.first_token_received = False
        
        # 将用户问题加入对话历史
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        # 准备请求参数
        self.payload = self._generate_payload(query)
        
        # 创建WebSocket连接
        url = self.create_url()
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        print(f"\n用户: {query}")
        print("\n星火: ", end="", flush=True)
        
        # 定义一个函数来运行WebSocket连接
        def run_websocket():
            try:
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            except Exception as e:
                print(f"WebSocket运行异常: {e}")
                self.done = True
        
        # 启动WebSocket连接
        ws_thread = thread.start_new_thread(run_websocket, ())
        
        # 等待回复完成
        timeout_counter = 0
        max_timeout = 300  # 30秒超时
        while not self.done:
            time.sleep(0.1)
            timeout_counter += 1
            if timeout_counter >= max_timeout:
                print("\n等待星火大模型响应超时，可能网络连接有问题")
                self.done = True
                break
        
        # 如果没有收到任何回复，但标记为完成了（可能是连接错误）
        if not self.current_response and self.done:
            self.current_response = "抱歉，星火大模型连接出现问题，无法获取回复。"
            # 移除刚才添加的对话，因为没有得到回复
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
        
        # 生成语音（如果TTS已初始化）- 保持同步调用
        if self.tts_initialized and self.current_response:
            try:
                print("\n大模型回复完成，开始语音合成...")
                self.tts_api.speak(self.current_response)
                
                # 输出提示，让用户知道程序在等待播放完成
                print("正在播放语音，请等待播放完成...")
                
                # 等待播放完成
                while not self.tts_api.is_playback_complete():
                    time.sleep(0.5)  # 每0.5秒检查一次
                    
                print("语音播放已完成，等待下一轮对话...")
                
                # 如果提供了回调函数，调用它
                if on_tts_complete:
                    on_tts_complete()
                    
            except Exception as e:
                print(f"\n语音合成出错: {e}")
                # 即使出错也调用回调函数
                if on_tts_complete:
                    on_tts_complete()
        else:
            # 如果没有TTS或没有响应内容，也调用回调函数
            if on_tts_complete:
                on_tts_complete()
        
        # 确保WebSocket已关闭
        try:
            self.ws.close()
        except:
            pass
                
        return self.current_response

# 用于测试的主函数
if __name__ == "__main__":
    spark = SparkAPI()
    
    print("==== 星火大模型对话测试 ====")
    print("输入'exit'退出，输入'reset'重置对话历史")
    
    while True:
        query = input("\n请输入问题: ")
        if query.lower() == "exit":
            break
        elif query.lower() == "reset":
            spark.reset_conversation()
            continue
            
        response = spark.chat(query)