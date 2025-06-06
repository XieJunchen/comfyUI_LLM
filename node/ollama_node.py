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

class ComfyUI_LLM_Ollama:
    """
    Ollama LLM集成节点
    
    特性：
    - 支持流式响应生成
    - 上下文记忆管理
    - 多线程安全访问
    - 动态模型列表加载
    - 详细的日志记录
    """
    # 在类定义顶部添加
    WEB_DIRECTORY = "./js"
    
    # 类级共享状态
    _conn_lock = Lock()
    _api_lock = Lock()
    _connection_checked = False
    _connection_status = False
    _available_models = ["llama3", "deepseek-r1:7b"]  # 默认值
    
    # 类级日志器 ✅ 修正点1
    logger = logging.getLogger("ComfyUI-Ollama")

    @classmethod
    def INPUT_TYPES(cls):
        """动态生成输入配置"""
        # 在类加载时尝试获取可用模型
        if not cls._connection_checked:
            cls._check_connection()
        
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "请用简洁的语言回答...",
                    "dynamicPrompts": False,
                    "lineCount": 4  # ✅ 初始显示4行高度
                }),
                "model": (cls._available_models, {"default": "deepseek-r1:7b"}),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "max_tokens": ("INT", {
                    "default": 1024,
                    "min": 1,
                    "max": 4096,
                    "step": 64,
                    "display": "number"
                }),
                "hide_thoughts": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "context": ("STRING", {"forceInput": True}),
                "system_message": ("STRING", {
                    "multiline": True,
                    "default": "你是有帮助的AI助手",
                    "lazy": True,
                    "lineCount": 3  # ✅ 初始显示3行高度
                }),
                "stop_sequences": ("STRING", {
                    "default": "",
                    "lazy": True
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("response", "context")
    FUNCTION = "generate"
    CATEGORY = "LLM"
    OUTPUT_NODE = False

    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.headers = {"Content-Type": "application/json"}
        self.timeout = 120
        self._init_logging()  # ✅ 修正点2：实例初始化日志配置

    def _init_logging(self):
        """初始化日志系统"""
        self.logger = logging.getLogger("ComfyUI-Ollama")
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(name)s] %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    @classmethod
    def _check_connection(cls):
        """类方法使用类级日志器 ✅ 修正点3"""
        with cls._conn_lock:
            if not cls._connection_checked:
                try:
                    # 使用类级日志器
                    cls.logger.info(f"🛠 正在检查Ollama连接...")
                    
                    response = requests.get(
                        "http://localhost:11434/api/tags",
                        timeout=10
                    )
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        cls._available_models = [m["name"] for m in models]
                        cls._connection_status = True
                        cls.logger.info(f"✅ 可用模型: {cls._available_models}")
                    else:
                        cls.logger.warning(f"连接失败，状态码：{response.status_code}")
                except Exception as e:
                    cls.logger.error(f"连接异常：{str(e)}")
                finally:
                    cls._connection_checked = True

    def _build_payload(self, **kwargs):
        """构造API请求负载"""
        stop_sequences = [s.strip() for s in kwargs['stop_sequences'].split(',')] if kwargs['stop_sequences'] else []
        
        return {
            "model": kwargs['model'],
            "prompt": kwargs['prompt'],
            "system": kwargs.get('system_message', '你是有帮助的AI助手'),
            "context": self._parse_context(kwargs.get('context')),
            "options": {
                "temperature": kwargs['temperature'],
                "num_predict": kwargs['max_tokens'],
                "stop": stop_sequences,
            }
        }

    def _parse_context(self, context: Optional[str]) -> List:
        """解析上下文数据"""
        try:
            return json.loads(context) if context else []
        except json.JSONDecodeError:
            self.logger.warning("上下文解析失败，使用空上下文")
            return []

    def _clean_response(self, text: str, hide_thoughts: bool) -> str:
        """响应后处理"""
        if hide_thoughts:
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text.strip()

    def generate(self, **kwargs):
        """主执行方法"""
        if not self._connection_status:
            return ("Ollama服务不可用，请检查", "")
            
        with self._api_lock:
            try:
                payload = self._build_payload(**kwargs)
                self.logger.debug(f"请求参数：{json.dumps(payload, indent=2)}")
                
                response_text = ""
                context = []
                
                with requests.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    headers=self.headers,
                    stream=True,
                    timeout=self.timeout
                ) as response:
                    response.raise_for_status()
                    
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line.decode('utf-8'))
                            response_text += data.get("response", "")
                            if data.get("done"):
                                context = data.get("context", [])
                
                cleaned_response = self._clean_response(response_text, kwargs['hide_thoughts'])
                self.logger.info(f"📥 响应长度: {len(cleaned_response)}字符")
                return (cleaned_response, json.dumps(context))
                
            except requests.RequestException as e:
                error_msg = f"API请求失败: {str(e)}"
                self.logger.error(error_msg)
                return (error_msg, "")
            except Exception as e:
                error_msg = f"处理错误: {str(e)}"
                self.logger.exception(error_msg)
                return (error_msg, "")

# 节点注册
NODE_CLASS_MAPPINGS = {
    "ComfyUI_LLM_Ollama": ComfyUI_LLM_Ollama
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyUI_LLM_Ollama": "🤖 Ollama LLM"
}