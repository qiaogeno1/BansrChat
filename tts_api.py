#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 语音合成API模块 (ffmpeg流式版本)
# 参考讯飞开放平台官方文档: 
# - 在线语音合成: https://www.xfyun.cn/doc/tts/online_tts/API.html
# - 超拟人语音合成: https://www.xfyun.cn/doc/spark/super%20smart-tts.html
#
# 使用前安装必要的依赖:
# pip install websocket-client python-dotenv

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import threading
import queue
import subprocess
import io
import sys
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time

import websocket
import dotenv
dotenv.load_dotenv()
dotenv.load_dotenv(override=True) 
# ====== TTS 模式设置 (在这里修改) ======
# True = 使用超拟人TTS，False = 使用普通TTS
USE_SUPER_TTS = False


class TTSApi:
    """
    讯飞在线语音合成API
    使用ffmpeg实现真正的流式播放
    """
    def is_playback_complete(self):
        """
        检查音频播放是否完成
        :return: True 表示播放已完成，False 表示正在播放
        """
        return not self.is_playing and self.audio_done
    def __init__(self, prepare=False):
        """
        初始化语音合成API参数
        """
        # 从环境变量获取讯飞API参数
        dotenv.load_dotenv()
        self.APPID = os.getenv("APPID")
        self.API_KEY = os.getenv("API_KEY")
        self.API_SECRET = os.getenv("API_SECRET")
        self.TTS_BASE_URL = os.getenv("TTS_BASE_URL")
        
        # 语音合成参数
        self.voice = os.getenv("TTS_VOICE", "xiaoyan")  # 发音人，默认为小燕
        
        # 安全地解析数值参数
        try:
            self.speed = int(os.getenv("TTS_SPEED", "50").strip())  # 语速，默认为50
        except ValueError:
            print(f"警告: TTS_SPEED 参数格式不正确，使用默认值 50")
            self.speed = 50
            
        try:
            self.volume = int(os.getenv("TTS_VOLUME", "70").strip())  # 音量，默认为70
        except ValueError:
            print(f"警告: TTS_VOLUME 参数格式不正确，使用默认值 70")
            self.volume = 70
            
        try:
            self.pitch = int(os.getenv("TTS_PITCH", "50").strip())  # 音高，默认为50
        except ValueError:
            print(f"警告: TTS_PITCH 参数格式不正确，使用默认值 50")
            self.pitch = 50
        
        # 使用全局配置
        self.use_super_tts = USE_SUPER_TTS
        
        if self.use_super_tts:
            # 超拟人TTS参数
            self.TTS_BASE_URL = os.getenv("SUPER_TTS_BASE_URL")
            self.voice_id = os.getenv("SUPER_TTS_VOICE_ID", "x4_lingxiaoli_oral")  # 默认使用灵小丽
            if isinstance(self.speed, float) and self.speed <= 2.0:
                # 如果速度是浮点数且在2.0以下，说明是旧的配置，转换为新格式（0-100）
                self.speed = int(self.speed * 50)  # 转换到大约等效的范围
        
        # 播放器相关参数
        self.is_playing = False
        self.audio_done = False
        
        # 音频数据队列，用于收集音频块
        self.audio_queue = queue.Queue()
        
        # 用于控制播放线程和ffmpeg进程
        self.ffmpeg_process = None
        self.playback_thread = None
        self.should_stop = threading.Event()
        self.connection_ready = False
        self.prepared_url = None
        
        # 如果需要预准备
        if prepare:
            self.prepare_connection()
    def _create_url(self):
        """
        生成WebSocket鉴权URL
        """
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 构建签名字符串
        host = urllib.parse.urlparse(self.TTS_BASE_URL).netloc
        path = urllib.parse.urlparse(self.TTS_BASE_URL).path
        
        # 生成RFC1123格式的时间戳
        signature_origin = f"host: {host}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {path} HTTP/1.1"
        
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
            "host": host
        }
        
        # 拼接URL
        url = self.TTS_BASE_URL + '?' + urllib.parse.urlencode(v)
        return url

    def _create_request_parameters(self, text):
        """
        创建请求参数
        :param text: 要合成的文本
        :return: 请求参数字典
        """
        if not self.use_super_tts:
            # 普通语音合成
            # 业务参数
            business_params = {
                "aue": "lame",  # 音频编码格式，lame表示mp3格式
                "sfl": 1,  # 是否开启流式返回
                "auf": "audio/L16;rate=16000",  # 音频采样率
                "vcn": self.voice,  # 发音人
                "speed": self.speed,  # 语速
                "volume": self.volume,  # 音量
                "pitch": self.pitch,  # 音高
                "bgs": 0,  # 是否有背景音乐，0表示无
                "tte": "UTF8"  # 文本编码格式
            }
            
            # 构建参数
            data = {
                "common": {
                    "app_id": self.APPID
                },
                "business": business_params,
                "data": {
                    "text": base64.b64encode(text.encode("utf-8")).decode(),
                    "status": 2  # 2表示完整的一段文本
                }
            }
            
            return data
        else:
            # 超拟人TTS
            # 构建参数 (使用正确的超拟人结构)
            data = {
                "header": {
                    "app_id": self.APPID,
                    "status": 2  # 表示完整的合成文本
                },
                "parameter": {
                    "oral": {  # 添加 oral 参数块
                        "oral_level": os.getenv("SUPER_TTS_ORAL_LEVEL", "mid") 
                    },
                    "tts": {
                        "vcn": os.getenv("SUPER_TTS_VOICE_ID", self.voice_id),  # 从env获取，或使用 self.voice_id
                        "speed": float(os.getenv("SUPER_TTS_SPEED", self.speed)),  # 语速
                        "volume": int(os.getenv("SUPER_TTS_VOLUME", self.volume)),  # 音量
                        "pitch": int(os.getenv("SUPER_TTS_PITCH", self.pitch)),  # 音高
                        "audio": {  # 添加 audio 参数块
                            "encoding": os.getenv("SUPER_TTS_ENCODING", "lame"),
                            "sample_rate": int(os.getenv("SUPER_TTS_SAMPLE_RATE", 24000)),
                            "channels": 1,
                            "bit_depth": 16
                        }
                    }
                },
                "payload": {
                    "text": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "status": 2,
                        "text": base64.b64encode(text.encode('utf-8')).decode('utf-8') 
                    }
                }
            }
            
            return data

    def _on_message(self, ws, message):
        """
        接收WebSocket消息的回调函数 (适配普通TTS和超拟人TTS)
        :param ws: WebSocket对象
        :param message: 接收到的消息
        """
        try:
            message = json.loads(message)
            
            code = -1  # 初始化错误码
            status = 1  # 初始化状态 (默认为中间帧)
            audio_data = ""  # 初始化音频数据

            if self.use_super_tts:
                # --- 解析超拟人TTS响应 ---
                header = message.get("header", {})
                code = header.get("code", 0)  # 从 header 获取 code
                status = header.get("status", 1)  # 从 header 获取 status
                
                if code != 0:
                    error_message = header.get("message", "未知错误")
                    print(f"超拟人语音合成错误 (Code: {code}): {error_message}")
                    ws.close()  # 出错时主动关闭连接
                    return
                
                # 从 payload 获取音频数据
                payload = message.get("payload", {})
                audio_payload = payload.get("audio", {})
                if audio_payload:  # 确保 audio 字段存在
                    audio_data = audio_payload.get("audio", "")
            
            else:
                # --- 解析普通在线TTS v2 响应 ---
                code = message.get("code", 0)  # 从顶级获取 code
                
                if code != 0:
                    error_message = message.get("message", "未知错误")
                    print(f"普通语音合成错误 (Code: {code}): {error_message}")
                    ws.close()  # 出错时主动关闭连接
                    return

                data_field = message.get("data", {})
                if data_field:  # 确保 data 字段存在
                    status = data_field.get("status", 1)  # 从 data 获取 status
                    audio_data = data_field.get("audio", "")  # 从 data 获取 audio

            # --- 通用处理 ---
            if audio_data:
                # 解码base64音频数据
                audio_bytes = base64.b64decode(audio_data)
                # 将音频数据添加到队列
                self.audio_queue.put(audio_bytes)
                
                # 如果尚未开始播放，启动播放线程
                if not self.is_playing:
                    print("收到第一个音频数据块，启动播放...")
                    self._start_playback()
            
            # 判断是否为最后一帧 (status == 2)
            if status == 2:
                print("语音合成完成，已收到所有数据")
                self.audio_done = True
                self.audio_queue.put(None)  # 放入结束标记
        
        except json.JSONDecodeError:
            print(f"无法解析收到的消息")
        except Exception as e:
            print(f"处理TTS消息时发生错误: {e}")
            ws.close()  # 发生未知错误时也尝试关闭连接

    def _on_error(self, ws, error):
        """
        WebSocket错误回调
        """
        print(f"语音合成连接错误: {error}")
        # 确保播放线程知道连接已结束
        self.audio_done = True
        self.audio_queue.put(None)  # 添加结束标记
    
    def _on_close(self, ws, close_status_code, close_msg):
        """
        WebSocket关闭回调
        """
        print(f"语音合成连接关闭")
    
    def _on_open(self, ws):
        """
        WebSocket连接建立回调
        """
        print("语音合成连接已建立")
        
        def send_data():
            """
            发送合成请求
            """
            try:
                ws.send(json.dumps(self.request_data))
            except Exception as e:
                print(f"发送语音合成请求失败: {str(e)}")
                ws.close()
        
        # 启动发送线程
        threading.Thread(target=send_data).start()

    def _start_playback(self):
        """
        启动ffmpeg实时播放流程
        """
        # 标记已开始播放
        self.is_playing = True
        
        # 创建并启动播放线程
        self.playback_thread = threading.Thread(target=self._stream_playback_thread)
        self.playback_thread.daemon = True
        self.playback_thread.start()

    def _stream_playback_thread(self):
        """
        使用ffmpeg实现流式播放的线程函数
        """
        try:
            print("启动ffmpeg播放线程")
            
            # 检查ffmpeg是否可用
            try:
                subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                print("错误: 找不到ffmpeg。请确保ffmpeg已安装并添加到PATH环境变量。")
                self.is_playing = False
                return
            
            # ffmpeg命令 - 从stdin读取MP3数据并实时播放
            # -i pipe:0 表示从标准输入读取
            # -low_delay 1 启用低延迟模式
            # -fflags nobuffer 禁用输入缓冲
            # -autoexit 音频播放完成后自动退出
            # -nodisp 不显示视频窗口
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # 覆盖输出文件
                "-f", "mp3",  # 指定输入格式为MP3
                "-i", "pipe:0",  # 从标准输入读取
                "-low_delay", "1",  # 启用低延迟模式
                "-fflags", "nobuffer",  # 禁用输入缓冲
                "-af", "atempo=1.0",  # 实时音频处理
                "-nodisp",  # 不显示视频窗口
                "-autoexit",  # 播放完成后自动退出
                "-f", "wav",  # 输出为WAV格式
                "pipe:1"  # 输出到标准输出
            ]

            # 针对不同操作系统选择不同的音频播放方式
            if sys.platform == "win32":  # Windows
                # 在Windows上，直接使用ffplay（ffmpeg自带播放器）更可靠
                ffmpeg_cmd = [
                    "ffplay",
                    "-nodisp",  # 不显示视频窗口
                    "-autoexit",  # 播放完成后自动退出
                    "-loglevel", "quiet",  # 减少日志输出
                    "-i", "pipe:0"  # 从标准输入读取
                ]
                
                # 创建单个ffplay进程来播放
                self.ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # 设置为无缓冲
                )
                
                # Windows上不需要额外的播放器进程
                play_process = None

            else:  # Linux和其他
                play_cmd = ["aplay", "-q"]
                
                # 创建ffmpeg进程，将标准输入和输出设为管道
                self.ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # 设置为无缓冲
                )
                
                # 创建播放器进程
                play_process = subprocess.Popen(
                    play_cmd,
                    stdin=self.ffmpeg_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # 设置为无缓冲
                )
                
                # 让ffmpeg将输出直接传给播放器
                self.ffmpeg_process.stdout.close()
            
            # 为非Windows平台创建进程
            if play_process is not None:
                # 让ffmpeg将输出直接传给播放器
                self.ffmpeg_process.stdout.close()
            
            # 实时将接收到的MP3数据传入ffmpeg
            while not self.should_stop.is_set():
                try:
                    # 从队列获取数据，最多等待0.5秒
                    audio_chunk = self.audio_queue.get(timeout=0.5)
                    
                    # 检查是否为结束标记
                    if audio_chunk is None:
                        print("收到结束标记，停止音频流")
                        break
                    
                    # 将数据写入ffmpeg进程
                    self.ffmpeg_process.stdin.write(audio_chunk)
                    self.ffmpeg_process.stdin.flush()  # 确保数据立即发送
                    
                except queue.Empty:
                    # 队列为空但合成尚未完成，继续等待
                    if not self.audio_done:
                        continue
                    else:
                        # 队列为空且合成已完成，结束循环
                        break
                except BrokenPipeError:
                    # ffmpeg进程可能已关闭
                    print("错误: 播放管道已中断")
                    break
                except Exception as e:
                    print(f"播放过程中发生错误: {e}")
                    break
            
            # 处理完所有数据后关闭stdin，通知ffmpeg输入结束
            try:
                if self.ffmpeg_process and self.ffmpeg_process.stdin:
                    self.ffmpeg_process.stdin.close()
            except Exception as e:
                print(f"关闭ffmpeg输入时出错: {e}")
            
            # 等待进程结束
            if self.ffmpeg_process:
                try:
                    # 关闭标准输入，通知ffmpeg输入结束
                    if self.ffmpeg_process.stdin:
                        self.ffmpeg_process.stdin.close()
                        
                    # 给予更长的等待时间，Windows上ffmpeg可能需要更多时间处理
                    exit_code = None
                    try:
                        exit_code = self.ffmpeg_process.wait(timeout=3)
                        print(f"ffmpeg进程已正常退出，退出代码: {exit_code}")
                    except subprocess.TimeoutExpired:
                        print("等待ffmpeg进程退出超时，将在清理资源时强制终止")
                except Exception as e:
                    print(f"等待ffmpeg进程时出错: {e}")

            if 'play_process' in locals() and play_process:
                try:
                    exit_code = play_process.wait(timeout=1)
                    print(f"播放器进程已退出，退出代码: {exit_code}")
                except subprocess.TimeoutExpired:
                    print("等待播放器进程退出超时，将在清理资源时强制终止")
                except Exception as e:
                    print(f"等待播放器进程时出错: {e}")

            # 调用_cleanup_resources方法确保所有资源被清理
            self._cleanup_resources()
            
        except Exception as e:
            print(f"播放线程发生异常: {e}")
        finally:
            # 确保清理所有资源
            self._cleanup_resources()
            self.is_playing = False
    
    def _cleanup_resources(self):
        """
        清理所有资源
        """
        # 终止ffmpeg进程
        if self.ffmpeg_process:
            try:
                print("正在关闭ffmpeg进程...")
                
                # 尝试先发送EOF信号 (关闭标准输入)
                if self.ffmpeg_process.stdin:
                    self.ffmpeg_process.stdin.close()
                
                # 给进程一些时间自行终止
                timeout = 1.0  # 等待时间(秒)
                start_time = time.time()
                while self.ffmpeg_process.poll() is None:
                    if time.time() - start_time > timeout:
                        break
                    time.sleep(0.1)
                
                # 如果进程仍在运行，则尝试正常终止
                if self.ffmpeg_process.poll() is None:
                    print("尝试正常终止ffmpeg进程...")
                    self.ffmpeg_process.terminate()
                    
                    # 再次等待一段时间
                    self.ffmpeg_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                print("ffmpeg进程未能正常终止，尝试强制终止...")
                try:
                    self.ffmpeg_process.kill()
                    self.ffmpeg_process.wait(timeout=0.5)
                    print("ffmpeg进程已强制终止")
                except Exception as e:
                    print(f"无法终止ffmpeg进程: {e}")
            except Exception as e:
                print(f"清理ffmpeg进程时出错: {e}")
                try:
                    # 最后尝试
                    if self.ffmpeg_process.poll() is None:
                        self.ffmpeg_process.kill()
                        print("已强制终止ffmpeg进程")
                except Exception:
                    pass
            
            self.ffmpeg_process = None
            print("ffmpeg资源已清理完毕")
    def prepare_connection(self):
        """
        预先准备TTS连接
        """
        try:
            self.prepared_url = self._create_url()
            self.connection_ready = True
            return True
        except Exception as e:
            print(f"准备TTS连接时出错: {e}")
            return False
    def speak(self, text, use_prepared=True):
        """
        将文本转换为语音并播放
        :param text: 要合成的文本
        """
        if not text:
            print("没有文本内容需要合成")
            return
        
        # 停止任何正在进行的播放
        self._stop_current_playback()
        
        # 重置状态
        self.is_playing = False
        self.audio_done = False
        self.audio_queue = queue.Queue()
        self.should_stop.clear()
        
        # 创建请求参数
        self.request_data = self._create_request_parameters(text)
        
        # 创建WebSocket URL
        if use_prepared and self.prepared_url:
            ws_url = self.prepared_url
        else:
            ws_url = self._create_url()
        
        # 创建WebSocket连接
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # 在新线程中运行WebSocket连接
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # 等待播放完成
        try:
            # 等待音频合成和播放完成
            max_wait_time = 60  # 最大等待时间，秒
            wait_step = 0.5  # 每次检查间隔
            wait_count = 0
            
            while self.is_playing or (not self.audio_done and wait_count * wait_step < max_wait_time):
                time.sleep(wait_step)
                wait_count += 1
            
            # 如果超时
            if not self.audio_done and wait_count * wait_step >= max_wait_time:
                print("等待语音合成完成超时")
            
            # 如果播放线程还在运行，等待其结束
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=2)
            
            print("语音合成和播放完成")
            
        except KeyboardInterrupt:
            print("用户中断了播放")
            self._stop_current_playback()
        except Exception as e:
            print(f"等待播放完成时出错: {e}")
            self._stop_current_playback()

    def _stop_current_playback(self):
        """
        停止当前正在进行的播放
        """
        if self.is_playing:
            print("停止当前播放...")
            self.should_stop.set()
            
            # 清空队列
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 添加结束标记
            self.audio_queue.put(None)
            
            # 清理资源
            self._cleanup_resources()
            
            # 等待播放线程结束
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=2)
            
            self.is_playing = False


# 测试代码
if __name__ == "__main__":
    # 测试语音合成
    tts = TTSApi()
    test_text = "你好，我在！"
    tts.speak(test_text)