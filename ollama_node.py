import requests
import json
import logging
import re
import os
import threading
from threading import Lock
from typing import Optional, List, Union, Dict, Any

# ----------------------------
# 日志系统配置
# ----------------------------
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
log_path = os.path.join(desktop_path, "ollama_comfyui.log")

# 强制删除旧日志
try:
    if os.path.exists(log_path):
        os.remove(log_path)
except Exception as e:
    print(f"旧日志删除失败: {str(e)}")

# 日志初始化
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())  # 控制台输出

# ----------------------------
# 核心实现类
# ----------------------------
class ComfyUI_LLM_Ollama:
    # 类级共享状态
    _conn_lock = Lock()     # 连接检查锁
    _api_lock = Lock()      # API请求锁
    _connection_checked = False
    _connection_status = False
    _available_models = []
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.headers = {"Content-Type": "application/json"}
        self.timeout = 120
        self._init_log_once()  # 确保日志提示只出现一次

    def _init_log_once(self):
        """确保日志路径提示只打印一次"""
        if not hasattr(self.__class__, '_log_initialized'):
            logger.info(f"📌 日志文件路径: {log_path}")
            print(f"👉 日志路径: {log_path} [仅首次提示]")
            self.__class__._log_initialized = True

    # ----------------------------
    # 连接管理
    # ----------------------------
    def _check_connection(self) -> bool:
        """线程安全的连接检查（带双重检查锁定）"""
        if self.__class__._connection_checked:
            return self.__class__._connection_status
            
        with self.__class__._conn_lock:
            if not self.__class__._connection_checked:
                try:
                    logger.debug(f"🛠 [{threading.current_thread().name}] 正在建立初始连接...")
                    resp = requests.get(f"{self.ollama_url}/api/tags", timeout=15)
                    models = resp.json().get("models", [])
                    self.__class__._available_models = [m["name"] for m in models]
                    self.__class__._connection_status = True
                    logger.info(f"✅ 可用模型: {', '.join(self._available_models)}")
                except Exception as e:
                    logger.error(f"❌ 连接失败: {str(e)}")
                    self.__class__._connection_status = False
                finally:
                    self.__class__._connection_checked = True
        return self.__class__._connection_status

    # ----------------------------
    # 核心处理逻辑
    # ----------------------------
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "请用简洁的语言回答..."}),
                "model": (["llama3", "deepseek-r1:7b", "mistral", "phi3"], {"default": "deepseek-r1:7b"}),
                "hide_thoughts": ("BOOLEAN", {"default": False}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": 1024, "min": 1, "max": 4096, "step": 1}),
            },
            "optional": {
                "context": ("STRING", {"forceInput": True}),
                "system_message": ("STRING", {"multiline": True, "default": "你是有帮助的AI助手"}),
                "stop_sequences": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("response", "context")
    FUNCTION = "generate_response"
    CATEGORY = "LLM"

    def _parse_context(self, context: Optional[Union[str, List]]) -> List:
        """解析上下文数据"""
        if not context:
            return []
        try:
            if isinstance(context, str):
                return json.loads(context) if context.strip() else []
            return list(context)
        except Exception as e:
            logger.warning(f"上下文解析失败: {str(e)}")
            return []

    def _clean_thoughts(self, text: str) -> str:
        """清理思考过程（支持跨行匹配）"""
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    def generate_response(self, 
                        prompt: str,
                        model: str,
                        hide_thoughts: bool,
                        temperature: float,
                        max_tokens: int,
                        context: Optional[str] = None,
                        system_message: Optional[str] = None,
                        stop_sequences: Optional[str] = None) -> tuple:
        """线程安全的响应生成入口"""
        # 连接检查
        if not self._check_connection():
            return ("⚠️ 连接异常，请检查Ollama服务", "[]")
            
        # API请求临界区保护
        with self.__class__._api_lock:
            thread_name = threading.current_thread().name
            logger.debug(f"🚦 [{thread_name}] 进入API临界区")
            
            try:
                # 构建请求参数
                stop_list = [s.strip() for s in stop_sequences.split(",")] if stop_sequences else []
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "system": system_message or "你是有帮助的AI助手",
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "stop": stop_list,
                    },
                    "context": self._parse_context(context),
                }
                logger.debug(f"📤 请求负载: {json.dumps(payload, indent=2, ensure_ascii=False)}")

                # 流式处理响应
                final_response = ""
                response_context = []
                try:
                    with requests.post(
                        f"{self.ollama_url}/api/generate",
                        headers=self.headers,
                        json=payload,
                        timeout=self.timeout,
                        stream=True
                    ) as resp:
                        resp.raise_for_status()
                        
                        for line in resp.iter_lines():
                            if line:
                                data = json.loads(line.decode('utf-8'))
                                if data.get("done", False):
                                    break
                                if "response" in data:
                                    final_response += data["response"]
                                if "context" in data:
                                    response_context = data["context"]
                                
                except requests.RequestException as e:
                    logger.error(f"🔴 请求失败: {str(e)}")
                    return (f"❌ 请求异常: {str(e)}", "[]")

                # 后处理
                if hide_thoughts:
                    final_response = self._clean_thoughts(final_response)
                
                logger.info(f"📥 响应长度: {len(final_response)}字符")
                return final_response, json.dumps(response_context)
                
            except Exception as e:
                logger.exception("💥 未捕获异常")
                return (f"❌ 系统错误: {str(e)}", "[]")
                
            finally:
                logger.debug(f"🚦 [{thread_name}] 退出API临界区")