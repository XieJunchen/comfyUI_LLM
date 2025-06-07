from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo
import requests
import torch
import numpy as np

class LoadImgFromUrl:
    """Load an image from the given URL"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": (
                    "STRING",
                    {
                        "default": "http://swqqsa5wv.hb-bkt.clouddn.com/admin/comfyui_b46dcb7133234c549218bf957a6334ed.png"
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load"
    CATEGORY = "云服务"
    
    def load(self, url):
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        image = Image.open(response.raw)
        image = ImageOps.exif_transpose(image)
        np_image = np.array(image).astype(np.float32) / 255.0
        if np_image.ndim == 2:  # 灰度图
            np_image = np.expand_dims(np_image, axis=-1)
        # 保证输出为 (1, H, W, C)
        tensor = torch.from_numpy(np_image).unsqueeze(0)
        return (tensor,)


class LoadGifFromLocal:
    """从本地路径加载GIF图片（返回所有帧的张量）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": (
                    "STRING",
                    {
                        "default": "your_local_gif_path.gif"
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "load"
    CATEGORY = "本地文件"

    def load(self, path):
        images = []
        with Image.open(path) as im:
            for frame in range(im.n_frames):
                im.seek(frame)
                frame_img = ImageOps.exif_transpose(im.convert("RGBA"))
                np_image = np.array(frame_img).astype(np.float32) / 255.0
                if np_image.ndim == 2:  # 灰度图
                    np_image = np.expand_dims(np_image, axis=-1)
                images.append(torch.from_numpy(np_image))
        # 输出为 (帧数, H, W, C)
        tensor = torch.stack(images, dim=0)
        return (tensor,)


NODE_CLASS_MAPPINGS = {
    "LoadImgFromUrl": LoadImgFromUrl,
    "LoadGifFromLocal": LoadGifFromLocal
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImgFromUrl": "☁️ 加载图片",
    "LoadGifFromLocal": "📂 加载本地GIF"
}