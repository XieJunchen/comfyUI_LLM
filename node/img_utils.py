from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo
import requests
import torch
import numpy as np
import os
import uuid
import tempfile
import subprocess
import imageio_ffmpeg


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


class ImagesToVideoAndUpload:
    """
    将图片张量序列合成为视频并上传到七牛云
    输入: 图片张量 (N, H, W, C)
    输出: 七牛云视频URL
    """
    @classmethod
    def INPUT_TYPES(cls):
        from .qiniu_uploader import load_qiniu_config
        config = load_qiniu_config() or {
            "access_key": "",
            "secret_key": "",
            "bucket_name": "",
            "domain": ""
        }
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": 12, "min": 1, "max": 60}),
                "access_key": ("STRING", {"default": config["access_key"]}),
                "secret_key": ("STRING", {"default": config["secret_key"]}),
                "bucket_name": ("STRING", {"default": config["bucket_name"]}),
                "domain": ("STRING", {"default": config["domain"]}),
                "folder": ("STRING", {"default": "video"}),
                "key_prefix": ("STRING", {"default": "comfyui_"}),
                "ext": (["mp4", "mov", "avi", "mkv"], {"default": "mp4"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "images_to_video_and_upload"
    CATEGORY = "云服务/七牛云"
    OUTPUT_NODE = True

    def images_to_video_and_upload(self, images, fps, access_key, secret_key, bucket_name, domain, folder, key_prefix, ext):
        from .qiniu_uploader import QiniuUploader
        # 1. 张量转图片序列（兼容 torch.Tensor 和 numpy）
        arr = images.cpu().numpy() if hasattr(images, 'cpu') else images
        img_list = [Image.fromarray(np.clip(255. * img, 0, 255).astype(np.uint8)) for img in arr]
        # 2. 只用 ffmpeg/imageio-ffmpeg 合成视频
        height, width = img_list[0].height, img_list[0].width
        pix_fmt = 'rgb24'
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmpfile:
            tmp_path = tmpfile.name
        cmd = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', pix_fmt,
            '-r', str(fps),
            '-i', '-',
            '-an',
            '-vcodec', 'libx264',
            '-pix_fmt', 'yuv420p',
            tmp_path
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for im in img_list:
            proc.stdin.write(im.convert('RGB').tobytes())
        proc.stdin.close()
        proc.wait()
        # 3. 上传到七牛云
        uploader = QiniuUploader(access_key, secret_key, bucket_name, domain)
        random_name = uuid.uuid4().hex
        folder_path = folder.strip().strip('/')
        key = f"{folder_path}/{key_prefix}{random_name}.{ext}"
        with open(tmp_path, "rb") as f:
            data = f.read()
        url = uploader.upload_binary(data, key)
        os.remove(tmp_path)
        return (url,)

NODE_CLASS_MAPPINGS = {
    "LoadImgFromUrl": LoadImgFromUrl,
    "LoadGifFromLocal": LoadGifFromLocal,
    "ImagesToVideoAndUpload": ImagesToVideoAndUpload
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImgFromUrl": "☁️ 加载图片",
    "LoadGifFromLocal": "📂 加载本地GIF",
    "ImagesToVideoAndUpload": "🖼️图片合成视频并上传七牛云"
}