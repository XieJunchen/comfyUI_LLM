import json
import traceback
from typing import Optional
from typing import Union

class StringArrayFormatter:
    """
    字符串数组处理节点
    
    功能：
    - 解析JSON格式字符串数组
    - 生成格式化统计报告
    - 自动验证输入格式
    - 支持自定义分隔符
    - 错误友好提示
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_str": ("STRING", {
                    "multiline": True,
                    "default": '["示例文本1", "示例文本2"]',
                    "dynamicPrompts": False
                }),
                "show_index": ("BOOLEAN", {"default": True}),
                "max_length": ("INT", {
                    "default": 200,
                    "min": 0,
                    "max": 1000,
                    "step": 50,
                    "display": "slider"
                }),
            },
            "optional": {
                "delimiter": ("STRING", {"default": "|", "lazy": True}),
            }
        }

    # 更新 RETURN_TYPES 和 RETURN_NAMES
    RETURN_TYPES = ( "INT", "LIST_STR")
    RETURN_NAMES = ("长度", "原始数组")
    FUNCTION = "format_array"
    CATEGORY = "LLM/文本处理"
    OUTPUT_NODE = True

    def _validate_input(self, input_str: str) -> Optional[list]:
        """输入验证与解析"""
        try:
            data = json.loads(input_str)
            if not isinstance(data, list):
                raise ValueError("输入不是数组格式")
            if not all(isinstance(item, str) for item in data):
                raise ValueError("数组包含非字符串元素")
            return data
        except json.JSONDecodeError:
            return None
        except Exception as e:
            print(f"❌ 输入验证失败: {str(e)}")
            return None

    def _format_item(self, index: int, text: str, delimiter: str, max_len: int) -> str:
        """单个元素的格式化处理"""
        # 截断处理
        display_text = text[:max_len] + "..." if len(text) > max_len else text
        
        # 转义分隔符
        safe_text = display_text.replace(delimiter, f"\\{delimiter}")
        
        # 添加索引
        if index >= 0:
            return f"[{index:02d}] {safe_text}"
        return safe_text

    def format_array(self, input_str: str, show_index: bool, max_length: int, delimiter: str = "|"):
        # 输入验证（调整后允许自动转换元素类型）
        str_array = []
        try:
            data = json.loads(input_str)
            if not isinstance(data, list):
                return ("⚠️ 输入必须是数组", 0, [])
            # 强制所有元素转为字符串
            str_array = [str(item) for item in data]
        except Exception as e:
            return (f"⚠️ 解析失败: {str(e)}", 0, [])

        # 返回原始数组和长度（新增第三个返回值）
        return (
            len(str_array),
            str_array  # 新增数组输出
        )

    @classmethod
    def IS_CHANGED(cls, input_str: str, **kwargs):
        """通过哈希值检测输入变化"""
        return hash(input_str)


class StringArrayIndexer:
    """
    字符串数组索引器（增强输入兼容性）
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_array": ("LIST_STR", {"forceInput": True}),
                "index": ("INT", {"default": 0}),
            },
            "optional": {
                "default_value": ("STRING", {"default": "🚫 无效索引"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_element"
    CATEGORY = "LLM/文本处理"

    def get_element(self, input_array, index, default_value="🚫 无效索引"):
        # 多模式解析
        parsed_list = self._parse_input(input_array)
        
        if not parsed_list:
            return (default_value,)
        
        # 处理负索引
        if index < 0:
            index += len(parsed_list)
        
        # 边界检查
        if 0 <= index < len(parsed_list):
            return (parsed_list[index],)
        
        return (default_value,)

    def _parse_input(self, raw_input):
        """支持解析多种格式的列表输入"""
        # 类型 1：直接列表输入
        if isinstance(raw_input, list):
            return [str(item) for item in raw_input]
            
        # 类型 2：JSON 字符串
        try:
            data = json.loads(raw_input)
            if isinstance(data, list):
                return [str(item) for item in data]
        except:
            pass
            
        # 类型 3：Python 风格列表字符串
        if raw_input.startswith("[") and raw_input.endswith("]"):
            try:
                return [
                    item.strip().strip("\"' ")
                    for item in raw_input[1:-1].split(",")
                ]
            except:
                pass
                
        return None

# 节点注册
NODE_CLASS_MAPPINGS = {
    "StringArrayIndexer": StringArrayIndexer,
    "StringArrayFormatter": StringArrayFormatter
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StringArrayIndexer": "📜 数组元素索引器",
    "StringArrayFormatter": "📜 文本数组格式化器"
}