#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 语音唤醒程序：使用Vosk监听唤醒词，然后启动语音助手对话
# 需要安装以下依赖:
# pip install vosk pyaudio dotenv

import os
import json
import pyaudio
import threading
import time
from vosk import Model, KaldiRecognizer
import dotenv
import sys
import array

# 导入语音助手模块中的相关组件
from tts_api import TTSApi
from spark_api import SparkAPI

# 从ASR1.5.py导入静音检测函数
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

# 加载环境变量
dotenv.load_dotenv()
dotenv.load_dotenv(override=True)

# 全局变量
wakeup_detected = False
vosk_running = True
asr_running = False
tts_api = None
spark_model = None

class VoskWakeup:
    """
    使用Vosk进行唤醒词检测
    """
    def __init__(self, model_path, wake_words=None):
        """
        初始化Vosk唤醒词检测
        :param model_path: Vosk模型路径
        :param wake_words: 唤醒词列表，默认为 ["一二三"]
        """
        self.model_path = model_path
        self.is_running = False
        self.wake_thread = None
        self.should_stop = threading.Event()
        
        # 设置默认唤醒词
        if wake_words is None:
            self.wake_words = ["你好小智", "你好小知", "小智小智", "小知小知"]
        else:
            self.wake_words = wake_words
            
        print(f"唤醒词设置为: {', '.join(self.wake_words)}")
        
        # 尝试加载模型
        try:
            self.model = Model(self.model_path)
            print(f"Vosk模型已加载: {self.model_path}")
        except Exception as e:
            print(f"加载Vosk模型出错: {e}")
            print("请确保您已下载Vosk模型并放置在正确的路径。")
            sys.exit(1)
    
    def start(self):
        """
        启动唤醒词监听
        """
        if not self.is_running:
            self.is_running = True
            self.should_stop.clear()
            
            # 创建并启动监听线程
            self.wake_thread = threading.Thread(target=self._listen_for_wakeword)
            self.wake_thread.daemon = True
            self.wake_thread.start()
            
            print("唤醒词监听已启动，等待唤醒...")
    
    def stop(self):
        """
        停止唤醒词监听
        """
        if self.is_running:
            print("正在停止唤醒词监听...")
            self.should_stop.set()
            self.is_running = False
            
            # 等待线程结束
            if self.wake_thread and self.wake_thread.is_alive():
                self.wake_thread.join(timeout=2)
            
            print("唤醒词监听已停止")
    
    def _listen_for_wakeword(self):
        """
        监听唤醒词的线程函数
        """
        global wakeup_detected, vosk_running
        
        # 音频参数
        CHUNK = 1280  # 每一帧的音频大小
        FORMAT = pyaudio.paInt16  # 16位深度
        CHANNELS = 1  # 单声道
        RATE = 16000  # 16000采样频率
        SILENCE_THRESHOLD = 500  # 静音检测阈值
        
        # 创建PyAudio对象
        p = pyaudio.PyAudio()
        
        try:
            # 创建语音识别器
            recognizer = KaldiRecognizer(self.model, RATE)
            recognizer.SetWords(True)  # 启用逐字识别
            
            # 打开音频流
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print("* 开始监听唤醒词...")
            
            while not self.should_stop.is_set():
                # 读取音频数据
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                # 如果有明显声音才进行处理（优化CPU使用）
                if not is_silent(data, SILENCE_THRESHOLD):
                    # 添加语音数据到识别器
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if "text" in result and result["text"]:
                            text = result["text"].lower()
                            print(f"识别到: {text}")
                            
                            # 检查是否包含唤醒词
                            for wake_word in self.wake_words:
                                if wake_word.lower() in text:
                                    print(f"检测到唤醒词: {wake_word}")
                                    wakeup_detected = True
                                    vosk_running = False
                                    self.should_stop.set()  # 设置停止标志
                                    break
                    
                    # 处理部分结果，用于实时反馈
                    partial_result = json.loads(recognizer.PartialResult())
                    if "partial" in partial_result and partial_result["partial"]:
                        partial_text = partial_result["partial"].lower()
                        
                        # 检查部分结果是否包含唤醒词
                        for wake_word in self.wake_words:
                            if wake_word.lower() in partial_text:
                                print(f"检测到唤醒词(部分识别): {wake_word}")
                                wakeup_detected = True
                                vosk_running = False
                                self.should_stop.set()  # 设置停止标志
                                break
                
                # 检查是否应该停止
                if wakeup_detected or self.should_stop.is_set():
                    break
                
            # 关闭流
            stream.stop_stream()
            stream.close()
        
        except Exception as e:
            print(f"唤醒词监听过程中出错: {e}")
        finally:
            p.terminate()
            self.is_running = False


def initialize_services():
    """
    预初始化TTS和Spark服务
    """
    global tts_api, spark_model
    
    print("正在初始化语音服务...")
    
    # 初始化TTS
    try:
        tts_api = TTSApi()
        # 预准备TTS连接
        tts_api.prepare_connection()
        print("TTS服务初始化成功")
    except Exception as e:
        print(f"TTS服务初始化失败: {e}")
        tts_api = None
    
    # 初始化Spark模型
    try:
        spark_model = SparkAPI(auto_connect=True)
        print("星火大模型初始化成功")
    except Exception as e:
        print(f"星火大模型初始化失败: {e}")
        spark_model = None


def handle_wakeup():
    """
    处理唤醒后的操作
    """
    global tts_api, spark_model, asr_running, vosk_running
    
    try:
        # 播放欢迎语
        if tts_api:
            print("播放欢迎语...")
            tts_api.speak("你好，我在！")
        else:
            print("TTS未能初始化，跳过欢迎语")
        
        # 设置对话标志
        asr_running = True
        
        # 导入ASR模块中的相关函数
        from ASR import voice_chat, continue_chat
        
        # 执行语音对话
        print("启动语音对话...")
        voice_chat_result = voice_chat()
        
        # 对话结束后，重置标志
        asr_running = False
        vosk_running = True
        
        print("语音对话已结束，重新启动唤醒词监听...")
    
    except Exception as e:
        print(f"处理唤醒时出错: {e}")
        # 确保重置标志
        asr_running = False
        vosk_running = True


def main():
    """
    主程序入口
    """
    global wakeup_detected, vosk_running, asr_running
    
    # 获取Vosk模型路径（从环境变量或使用默认值）
    vosk_model_path = os.getenv("VOSK_MODEL_PATH", "./vosk-model-small-cn")
    
    # 获取唤醒词（从环境变量或使用默认值）
    wake_words_str = os.getenv("WAKE_WORDS", "一二三,你好小知,小智小智,小知小知")
    wake_words = [word.strip() for word in wake_words_str.split(",")]
    
    # 初始化服务
    initialize_services()
    
    # 创建唤醒检测器
    wakeup_detector = VoskWakeup(vosk_model_path, wake_words)
    
    print("==== 语音唤醒 + 语音助手系统 ====")
    print(f"唤醒词: {', '.join(wake_words)}")
    print("请说唤醒词来启动助手")
    
    try:
        # 主循环
        while True:
            # 监听唤醒词
            if vosk_running and not asr_running:
                wakeup_detected = False
                wakeup_detector.start()
                
                # 等待唤醒检测器停止（被唤醒或手动停止）
                while wakeup_detector.is_running:
                    time.sleep(0.1)
            
            # 如果检测到唤醒词，处理唤醒
            if wakeup_detected:
                handle_wakeup()
                wakeup_detected = False
            
            # 短暂等待，避免CPU过度使用
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n收到键盘中断，程序正在退出...")
    except Exception as e:
        print(f"\n程序发生错误: {e}")
    finally:
        # 确保停止唤醒检测器
        if wakeup_detector.is_running:
            wakeup_detector.stop()
        
        print("\n程序已退出")


if __name__ == "__main__":
    main()
