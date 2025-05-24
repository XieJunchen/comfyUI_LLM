import qiniu
import os
from qiniu import Auth, put_data
import io
from PIL import Image
import numpy as np
import uuid

class QiniuUploader:
    def __init__(self, access_key: str, secret_key: str, bucket_name: str, domain: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.domain = domain
        self.q = Auth(self.access_key, self.secret_key)

    def upload_binary(self, data: bytes, key: str = None) -> str:
        """
        上传二进制数据到七牛云
        :param data: 二进制内容
        :param key: 文件名（可选），不传则由七牛自动生成
        :return: 文件外链URL
        """
        token = self.q.upload_token(self.bucket_name, key, 3600)
        ret, info = put_data(token, key, data)
        print(f"七牛 put_data 返回 ret: {ret}, info: {info}")  # 打印上传结果
        # 七牛 put_data 返回 ret 可能为 None，info.key 才是真实 key
        real_key = None
        if ret is not None and 'key' in ret:
            real_key = ret['key']
        elif hasattr(info, 'key') and info.key:
            real_key = info.key
        if real_key:
            url = f"{self.domain}/{real_key}"
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "http://" + url.lstrip("/")
            return url
        else:
            raise Exception(f"上传失败: {info}")

class QiniuImageUploadNode:
    """
    ComfyUI 图片张量直接上传七牛云节点
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "access_key": ("STRING", {"default": ""}),
                "secret_key": ("STRING", {"default": ""}),
                "bucket_name": ("STRING", {"default": ""}),
                "domain": ("STRING", {"default": ""}),
                "images": ("IMAGE", ),
                "key_prefix": ("STRING", {"default": "comfyui_"}),
                "format": (["PNG", "JPEG"], {"default": "PNG"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("urls",)
    FUNCTION = "upload_images"
    CATEGORY = "云服务/七牛云"
    OUTPUT_NODE = True

    def upload_images(self, access_key, secret_key, bucket_name, domain, images, key_prefix, format):
        uploader = QiniuUploader(access_key, secret_key, bucket_name, domain)
        urls = []
        arr = images.cpu().numpy() if hasattr(images, 'cpu') else images
        for idx, image in enumerate(arr):
            img = Image.fromarray(np.clip(255. * image, 0, 255).astype(np.uint8))
            buf = io.BytesIO()
            img.save(buf, format=format)
            buf.seek(0)
            random_name = uuid.uuid4().hex
            key = f"{key_prefix}{random_name}.{format.lower()}"
            url = uploader.upload_binary(buf.getvalue(), key)
            print(f"上传图片返回 url: {url}, 类型: {type(url)}")
            urls.append(str(url))
        return (urls,)

class ShowUrlsNode:
    """
    展示图片外链地址节点
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "urls": ("LIST_STR", ),
            }
        }

    RETURN_TYPES = ("LIST_STR",)
    RETURN_NAMES = ("urls",)
    FUNCTION = "show"
    CATEGORY = "展示/调试"
    OUTPUT_NODE = True

    def show(self, urls):
        # 直接返回输入，便于在 ComfyUI history API 查询
        return (urls,)

NODE_CLASS_MAPPINGS = {
    "QiniuImageUploadNode": QiniuImageUploadNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
"QiniuImageUploadNode": "☁️ 七牛云图片上传 (IMAGE)",
}
