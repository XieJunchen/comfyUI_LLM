from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo
import requests
import numpy as np

class LoadImageFromUrl:
    """Load an image from the given URL"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": (
                    "STRING",
                    {
                        "default": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Example.jpg/800px-Example.jpg"
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load"
    CATEGORY = "云服务"
    
    
    def load(self, url):
        # 下载图片
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        image = Image.open(response.raw)
        image = ImageOps.exif_transpose(image)
        # 转为 numpy 格式，float32，范围0~1，shape为(H, W, C)
        np_image = np.array(image).astype(np.float32) / 255.0
        if np_image.ndim == 2:  # 灰度图
            np_image = np.expand_dims(np_image, axis=-1)
        return (np_image,)

NODE_CLASS_MAPPINGS = {
    "LoadImageFromUrl": LoadImageFromUrl
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromUrl": "☁️ 加载图片"
}