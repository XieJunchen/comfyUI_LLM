import os
from qiniu import Auth, put_data
import io
from PIL import Image
import numpy as np
import uuid
import os
import uuid
import tempfile
import subprocess
import imageio_ffmpeg
from ..cloud_utils import load_cloud_config, CloudUploader


class QiniuUploader:
    def __init__(self, access_key: str, secret_key: str, bucket_name: str, domain: str,):
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

# class JDCloudUploader(CloudUploader):
#     """
#     京东云对象存储上传实现（需安装 jdcloud-sdk-python）
#     """
#     def __init__(self, access_key: str, secret_key: str, bucket_name: str, domain: str, region: str = "cn-north-1"):
#         from jdcloud_sdk.services.oss.client.OssClient import OssClient
#         from jdcloud_sdk.core.credential import Credential
#         self.access_key = access_key
#         self.secret_key = secret_key
#         self.bucket_name = bucket_name
#         self.domain = domain
#         self.region = region
#         self.credential = Credential(self.access_key, self.secret_key)
#         self.client = OssClient(self.credential)

#     def upload_binary(self, data: bytes, key: str = None) -> str:
#         if not key:
#             import uuid
#             key = uuid.uuid4().hex
#         resp = self.client.put_object(self.bucket_name, key, body=data)
#         if hasattr(resp, "error") and resp.error:
#             raise Exception(f"京东云上传失败: {resp.error}")
#         url = f"{self.domain}/{key}"
#         if not url.startswith("http://") and not url.startswith("https://"):
#             url = "http://" + url.lstrip("/")
#         return url

class CloudImageUploadNode:
    """
    ComfyUI 图片张量直接上传云节点
    """
    @classmethod
    def INPUT_TYPES(cls):
        cloud_type, config = load_cloud_config()
        return {
            "required": {
                "access_key": ("STRING", {"default": config.get("access_key", "")}),
                "secret_key": ("STRING", {"default": config.get("secret_key", "")}),
                "bucket_name": ("STRING", {"default": config.get("bucket_name", "")}),
                "domain": ("STRING", {"default": config.get("domain", "")}),
                "images": ("IMAGE", ),
                "folder": ("STRING", {"default": "output"}),
                "key_prefix": ("STRING", {"default": "comfyui_"}),
                "format": (["PNG", "JPEG", "GIF"], {"default": "PNG"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("urls",)
    FUNCTION = "upload_images"
    CATEGORY = "云服务"
    OUTPUT_NODE = True

    def upload_images(self, access_key, secret_key, bucket_name, domain, images, folder, key_prefix, format):
        cloud_type, _ = load_cloud_config()
        if cloud_type == "jdcloud":
            # uploader = JDCloudUploader(access_key, secret_key, bucket_name, domain)
            raise NotImplementedError(f"暂不支持的云类型: {cloud_type}")
        else:
            uploader = QiniuUploader(access_key, secret_key, bucket_name, domain)
        urls = []
        arr = images.cpu().numpy() if hasattr(images, 'cpu') else images
        for idx, image in enumerate(arr):
            img = Image.fromarray(np.clip(255. * image, 0, 255).astype(np.uint8))
            buf = io.BytesIO()
            if format == "GIF":
                img = img.convert("P", palette=Image.ADAPTIVE)
                img.save(buf, format="GIF")
            else:
                img.save(buf, format=format)
            buf.seek(0)
            random_name = uuid.uuid4().hex
            # 拼接文件夹路径
            folder_path = folder.strip().strip('/')
            key = f"{folder_path}/{key_prefix}{random_name}.{format.lower()}"
            url = uploader.upload_binary(buf.getvalue(), key)
            print(f"上传图片返回 url: {url}, 类型: {type(url)}")
            urls.append(str(url))
        return (urls,)

class CloudVideoUploadNode:
    """
    ComfyUI 视频文件上传云节点
    """
    @classmethod
    def INPUT_TYPES(cls):
        cloud_type, config = load_cloud_config()
        return {
            "required": {
                "access_key": ("STRING", {"default": config.get("access_key", "")}),
                "secret_key": ("STRING", {"default": config.get("secret_key", "")}),
                "bucket_name": ("STRING", {"default": config.get("bucket_name", "")}),
                "domain": ("STRING", {"default": config.get("domain", "")}),
                "video_path": ("STRING", {"default": ""}),
                "folder": ("STRING", {"default": "video"}),
                "key_prefix": ("STRING", {"default": "comfyui_"}),
                "ext": (["mp4", "mov", "avi", "mkv"], {"default": "mp4"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "upload_video"
    CATEGORY = "云服务"
    OUTPUT_NODE = True

    def upload_video(self, access_key, secret_key, bucket_name, domain, video_path, folder, key_prefix, ext):
        cloud_type, _ = load_cloud_config()
        if cloud_type == "jdcloud":
            # uploader = JDCloudUploader(access_key, secret_key, bucket_name, domain)
            raise NotImplementedError(f"暂不支持的云类型: {cloud_type}")
        else:
            uploader = QiniuUploader(access_key, secret_key, bucket_name, domain)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        with open(video_path, "rb") as f:
            data = f.read()
        random_name = uuid.uuid4().hex
        folder_path = folder.strip().strip('/')
        key = f"{folder_path}/{key_prefix}{random_name}.{ext}"
        url = uploader.upload_binary(data, key)
        print(f"上传视频返回 url: {url}, 类型: {type(url)}")
        return (url,)

class CloudImagesToVideoAndUpload:
    """
    将图片张量序列合成为视频并上传到云存储（支持多云扩展）
    输入: 图片张量 (N, H, W, C)
    输出: 云存储视频URL
    """
    @classmethod
    def INPUT_TYPES(cls):
        cloud_type, config = load_cloud_config()
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": 12, "min": 1, "max": 60}),
                "cloud_type": ("STRING", {"default": cloud_type}),
                "access_key": ("STRING", {"default": config["access_key"]}),
                "secret_key": ("STRING", {"default": config["secret_key"]}),
                "bucket_name": ("STRING", {"default": config["bucket_name"]}),
                "domain": ("STRING", {"default": config["domain"]}),
                "folder": ("STRING", {"default": "video"}),
                "key_prefix": ("STRING", {"default": "comfyui_"}),
                "ext": (["mp4", "mov", "avi", "mkv"], {"default": "mp4"}),
                "audio": ("AUDIO", {"default": None}),  # 改为AUDIO类型
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "images_to_video_and_upload"
    CATEGORY = "云服务"
    OUTPUT_NODE = True

    def images_to_video_and_upload(self, images, fps, cloud_type, access_key, secret_key, bucket_name, domain, folder, key_prefix, ext, audio=None):
        import torchaudio
        config = load_cloud_config()[1]
        access_key = access_key or config.get("access_key", "")
        secret_key = secret_key or config.get("secret_key", "")
        bucket_name = bucket_name or config.get("bucket_name", "")
        domain = domain or config.get("domain", "")
        # 1. 张量转图片序列
        arr = images.cpu().numpy() if hasattr(images, 'cpu') else images
        img_list = [Image.fromarray(np.clip(255. * img, 0, 255).astype(np.uint8)) for img in arr]
        # 2. 合成视频
        height, width = img_list[0].height, img_list[0].width
        pix_fmt = 'rgb24'
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmpfile:
            tmp_path = tmpfile.name
        # 先生成无音频视频，临时文件名用 _noaudio 结尾但扩展名标准
        tmp_video_path = tmp_path.replace(f'.{ext}', f'_noaudio.{ext}')
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
            tmp_video_path
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for im in img_list:
            proc.stdin.write(im.convert('RGB').tobytes())
        proc.stdin.close()
        proc.wait()
        # 如果有AUDIO，保存为wav临时文件再合成
        if audio is not None and isinstance(audio, dict) and "waveform" in audio and "sample_rate" in audio:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
                audio_path = tmp_audio.name
            waveform = audio["waveform"]
            sample_rate = audio["sample_rate"]
            # waveform shape: (1, channels, samples) or (channels, samples)
            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)
            torchaudio.save(audio_path, waveform, sample_rate)
            # 合成音视频到tmp_path
            merge_cmd = [
                imageio_ffmpeg.get_ffmpeg_exe(),
                '-y',
                '-i', tmp_video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                tmp_path
            ]
            subprocess.run(merge_cmd, check=True)
            os.remove(tmp_video_path)
            os.remove(audio_path)
        else:
            # 无音频直接重命名
            os.rename(tmp_video_path, tmp_path)
        # 3. 上传到云存储
        if cloud_type == "qiniu":
            uploader = QiniuUploader(access_key, secret_key, bucket_name, domain)
        elif cloud_type == "jdcloud":
            # uploader = JDCloudUploader(access_key, secret_key, bucket_name, domain)
            raise NotImplementedError(f"暂不支持的云类型: {cloud_type}")
        random_name = uuid.uuid4().hex
        folder_path = folder.strip().strip('/')
        key = f"{folder_path}/{key_prefix}{random_name}.{ext}"
        with open(tmp_path, "rb") as f:
            data = f.read()
        url = uploader.upload_binary(data, key)
        os.remove(tmp_path)
        return (url,)

# 注册到节点映射
NODE_CLASS_MAPPINGS = {
    "CloudImageUploadNode": CloudImageUploadNode,
    "CloudVideoUploadNode": CloudVideoUploadNode,
    "CloudImagesToVideoAndUpload": CloudImagesToVideoAndUpload
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CloudImageUploadNode": "☁️ 图片上传到云 (IMAGE)",
    "CloudVideoUploadNode": "☁️ 视频上传到云 (VIDEO)",
    "CloudImagesToVideoAndUpload": "🖼️图片合成视频并上传到云"
}
