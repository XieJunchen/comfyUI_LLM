import os
import json


def load_cloud_config(config_path=None):
    """
    通用多云配置读取工具方法，返回 (cloud_type, config) 元组。
    config_path 可选，默认自动定位到 cloud_config.json。
    """
    if config_path is None:
        # 优先本目录下 cloud_config.json
        local_path = os.path.join(os.path.dirname(__file__), "cloud_config.json")
        parent_path = os.path.join(os.path.dirname(__file__), "..", "cloud_config.json")
        if os.path.exists(local_path):
            config_path = local_path
        elif os.path.exists(parent_path):
            config_path = parent_path
        else:
            # 返回空配置，避免节点加载时报错
            return "qiniu", {"access_key": "", "secret_key": "", "bucket_name": "", "domain": ""}
    if not os.path.exists(config_path):
        return "qiniu", {"access_key": "", "secret_key": "", "bucket_name": "", "domain": ""}
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    cloud_type = config.get("cloud_type", "qiniu")
    cloud_config = config.get(cloud_type, {})
    return cloud_type, cloud_config


class CloudUploader:
    """
    云存储上传抽象基类，所有云厂商需实现 upload_binary 方法
    """

    def upload_binary(self, data: bytes, key: str = None) -> str:
        raise NotImplementedError("upload_binary 必须由子类实现")