import os
import json
import logging
from typing import Optional, List
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk

# ----------------------------
# 日志系统配置
# ----------------------------
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
log_path = os.path.join(desktop_path, "deepseek_comfyui.log")

logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w'
)
logger = logging.getLogger("ComfyUI-DeepSeek")
logger.addHandler(logging.StreamHandler())

class ComfyUI_LLM_Online:
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": "", "password": True}),
                "input_str": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "model": (["deepseek-chat", "deepseek-coder","deepseek-reasoner"], {"default": "deepseek-chat"}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "stop_sequences": ("STRING", {"default": ""}),
                "stream_mode": (["enable", "disable"], {"default": "disable"}),
            },
            "optional": {
                "system_prompt": ("STRING", {"default": "你是有帮助的AI助手", "multiline": True}),
                "context": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("response",)
    FUNCTION = "query_llm"
    CATEGORY = "LLM"
    OUTPUT_NODE = True

    def _validate_inputs(self, **kwargs):
        """参数验证"""
        if not kwargs.get("api_key"):
            raise ValueError("API密钥不能为空")
        
        if len(kwargs.get("input_str", "").strip()) < 2:
            raise ValueError("输入内容过短（至少需要2个字符）")

        if not 0 <= kwargs.get("temperature", 0.7) <= 1:
            raise ValueError("温度参数需在0-1之间")

    def _build_messages(self, **kwargs):
        """构造消息历史"""
        messages = []
        
        # 系统提示
        if system_prompt := kwargs.get("system_prompt"):
            messages.append({"role": "system", "content": system_prompt})
        
        # 上下文历史
        if context := kwargs.get("context"):
            try:
                history = json.loads(context)
                if isinstance(history, list):
                    messages.extend(history)
            except json.JSONDecodeError:
                logger.warning("上下文解析失败，使用原始字符串")
                messages.append({"role": "user", "content": context})
        
        # 当前输入
        messages.append({"role": "user", "content": kwargs["input_str"]})
        return messages

    def _handle_stream_response(self, stream: Stream[ChatCompletionChunk]) -> str:
        """处理流式响应"""
        full_response = []
        for chunk in stream:
            if content := chunk.choices[0].delta.content:
                full_response.append(content)
                yield content  # 实时输出
        
        logger.debug(f"完整响应：{''.join(full_response)}")
        return ''.join(full_response)

    def query_llm(self, **kwargs):
        try:
            # 输入验证
            self._validate_inputs(**kwargs)
            
            # 初始化客户端
            client = OpenAI(
                api_key=kwargs["api_key"],
                base_url="https://api.deepseek.com/v1",
            )
            
            # 构造请求参数
            stop_sequences = [s.strip() for s in kwargs["stop_sequences"].split(",") if s.strip()]
            
            # 创建API请求
            response = client.chat.completions.create(
                model=kwargs["model"],
                messages=self._build_messages(**kwargs),
                temperature=kwargs["temperature"],
                max_tokens=kwargs["max_tokens"],
                stop=stop_sequences if stop_sequences else None,
                stream=kwargs["stream_mode"] == "enable",
            )
            
            # 处理响应
            if isinstance(response, Stream):
                # 流式处理
                return (self._handle_stream_response(response),)
            
            # 普通响应
            content = response.choices[0].message.content
            logger.debug(f"API响应：{content}")
            return (content,)
            
        except Exception as e:
            logger.error(f"API请求失败：{str(e)}", exc_info=True)
            return (f"错误：{str(e)}",)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """通过哈希值检测输入变化"""
        return hash(json.dumps(kwargs, sort_keys=True))

# 节点注册
NODE_CLASS_MAPPINGS = {
    "DeepSeek_Online": ComfyUI_LLM_Online
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DeepSeek_Online": "🧠 DeepSeek 智能助手"
}