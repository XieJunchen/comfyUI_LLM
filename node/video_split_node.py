import cv2
import torch
import numpy as np
 
import tempfile
import subprocess
import os

class SplitVideoByFrames:
    """
    用OpenCV拆分视频为多个片段，每段帧数不超过max_frames_per_clip，音频输出为ComfyUI官方格式
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path": ("STRING", {"default": "your_video.mp4"}),
                "max_frames_per_clip": ("INT", {"default": 30, "min": 1, "max": 1000}),
            }
        }

    RETURN_TYPES = ("INT", "LIST", "AUDIO")
    RETURN_NAMES = ("num_clips", "clips", "audio")
    FUNCTION = "split_video"
    CATEGORY = "云服务"

    def split_video(self, video_path, max_frames_per_clip):
        # 1. 提取音频为wav临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            audio_path = tmp_audio.name
        ffmpeg_bin = "ffmpeg"  # 假设已在环境变量
        cmd = [ffmpeg_bin, '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', '-f', 'wav', audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # 检查音频文件是否有效
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            print(f"警告：视频 {video_path} 无音轨或音频提取失败，返回空音频。")
            waveform = torch.zeros((1, 2, 1), dtype=torch.float32)  # 1帧2通道空音频
            sample_rate = 44100
            audio_dict = {"waveform": waveform, "sample_rate": sample_rate}
        else:
            try:
                import torchaudio
                waveform, sample_rate = torchaudio.load(audio_path)
            except Exception as e:
                print(f"警告：音频文件读取失败，返回空音频。错误信息: {e}")
                waveform = torch.zeros((1, 2, 1), dtype=torch.float32)
                sample_rate = 44100
            audio_dict = {"waveform": waveform, "sample_rate": sample_rate}
        os.remove(audio_path)
        # 保证shape为(1,channels,samples)
        if waveform.dim() == 2:
            waveform = waveform.unsqueeze(0)
        audio_dict = {"waveform": waveform, "sample_rate": sample_rate}

        # 3. 视频分帧（不做resize，假设视频分辨率一致）
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频文件: {video_path}")
        frames = []
        clips = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            np_image = frame.astype(np.float32) / 255.0
            frames.append(torch.from_numpy(np_image))
            if len(frames) == max_frames_per_clip:
                clips.append({"frames": torch.stack(frames, dim=0), "audio": audio_dict})
                frames = []
        if frames:
            clips.append({"frames": torch.stack(frames, dim=0), "audio": audio_dict})
        cap.release()
        return (len(clips), clips, audio_dict)

class GetVideoClipByIndex:
    """
    输入clips和索引，输出该片段的图片数组（IMAGE）、音频（官方格式）和帧数（num_frames）
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "index": ("INT", {"default": 0, "min": 0}),
                "clips": ("LIST", {}),
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "INT")
    RETURN_NAMES = ("images", "audio", "num_frames")
    FUNCTION = "get_clip"
    CATEGORY = "云服务"

    def get_clip(self, index, clips):
        if not clips or index < 0 or index >= len(clips):
            raise IndexError("索引超出clips范围")
        clip = clips[index]
        frames = clip["frames"]
        audio = clip["audio"]
        print(f"获取片段 {index}，帧数: {frames.shape[0]}, 音频采样率: {audio['sample_rate']}")
        num_frames = frames.shape[0]
        return (frames, audio, num_frames)

class CreateEmptyImageBatch:
    """
    创建一个空的图像batch，若传入images则追加到空batch后返回。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "images": ("IMAGE", {}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_batch",)
    FUNCTION = "create"
    CATEGORY = "云服务/集合工具"

    def create(self, images=None):
        import torch
        def to_3ch(img):
            if img is None:
                return img
            if img.dim() == 3:
                if img.shape[-1] == 1:
                    img = img.repeat(1, 1, 3)
                elif img.shape[-1] == 4:
                    img = img[..., :3]
            elif img.dim() == 4:
                if img.shape[-1] == 1:
                    img = img.repeat(1, 1, 1, 3)
                elif img.shape[-1] == 4:
                    img = img[..., :3]
            return img
        batch = torch.empty((0, 0, 0, 0), dtype=torch.float32)
        if images is not None:
            images = to_3ch(images)
            if images.dim() == 3:
                images = images.unsqueeze(0)
            # 直接用AppendImagesToBatch的逻辑拼接
            if batch.numel() == 0 or batch.shape[0] == 0:
                return (images,)
            else:
                new_batch = torch.cat([batch, images], dim=0)
                return (new_batch,)
        return (batch,)

class AppendImagesToBatch:
    """
    向已有图像batch追加图片，支持单张或多张图片，输出合并后的IMAGE batch。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_batch": ("IMAGE", {}),
                "images_to_add": ("IMAGE", {}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_batch",)
    FUNCTION = "append"
    CATEGORY = "云服务/集合工具"

    def append(self, image_batch, images_to_add):
        import torch
        # 如果 image_batch 是空的（shape为(0, 0, 0, 0)），直接返回 images_to_add
        if image_batch.numel() == 0 or image_batch.shape[0] == 0:
            if images_to_add.dim() == 3:
                images_to_add = images_to_add.unsqueeze(0)
            return (images_to_add,)
        if image_batch.dim() == 3:
            image_batch = image_batch.unsqueeze(0)
        if images_to_add.dim() == 3:
            images_to_add = images_to_add.unsqueeze(0)
        new_batch = torch.cat([image_batch, images_to_add], dim=0)
        return (new_batch,)

class GetFirstImageFromBatch:
    """
    获取图片batch的首帧或末帧，输出单帧IMAGE batch（shape为(1, H, W, C)）及宽高。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_batch": ("IMAGE", {}),
                "mode": (["first", "last"], {"default": "first"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "get"
    CATEGORY = "云服务/集合工具"

    def get(self, image_batch, mode="first"):
        import torch
        if image_batch.dim() == 3:
            img = image_batch.unsqueeze(0)
        else:
            if image_batch.shape[0] == 0:
                raise ValueError("image_batch is empty!")
            if mode == "first":
                img = image_batch[0:1]
            else:
                img = image_batch[-1:]
        # img shape: (1, H, W, C)
        _, h, w, _ = img.shape
        return (img, w, h)

class RemoveFirstOrLastImageFromBatch:
    """
    删除图片batch的首帧或末帧，输出剩余IMAGE batch。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_batch": ("IMAGE", {}),
                "mode": (["first", "last"], {"default": "first"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_batch",)
    FUNCTION = "remove"
    CATEGORY = "云服务/集合工具"

    def remove(self, image_batch, mode="first"):
        import torch
        if image_batch.dim() == 3:
            # 只有一张，删除后为空batch
            return (torch.empty((0, *image_batch.shape), dtype=image_batch.dtype, device=image_batch.device),)
        if image_batch.shape[0] == 0:
            return (image_batch,)
        if mode == "first":
            return (image_batch[1:],)
        else:
            return (image_batch[:-1],)

NODE_CLASS_MAPPINGS = {
    "SplitVideoByFrames": SplitVideoByFrames,
    "GetVideoClipByIndex": GetVideoClipByIndex,
    "CreateEmptyImageBatch": CreateEmptyImageBatch,
    "AppendImagesToBatch": AppendImagesToBatch,
    "GetFirstImageFromBatch": GetFirstImageFromBatch,
    "RemoveFirstOrLastImageFromBatch": RemoveFirstOrLastImageFromBatch
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SplitVideoByFrames": "🎬 视频分段拆帧",
    "GetVideoClipByIndex": "🖼️ 获取片段图片和音频",
    "CreateEmptyImageBatch": "📂 创建空图像Batch",
    "AppendImagesToBatch": "➕ 追加图片到Batch",
    "GetFirstImageFromBatch": "🔍 获取首/末帧图片",
    "RemoveFirstOrLastImageFromBatch": "❌ 删除首/末帧图片"
}