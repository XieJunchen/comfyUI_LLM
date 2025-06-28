import cv2
import torch
import numpy as np

class SplitVideoByFrames:
    """
    传入视频路径，根据帧率将视频拆分为多段，每段帧数上限可控，输出为张量序列列表
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path": ("STRING", {"default": "your_video.mp4"}),
                "max_frames_per_clip": ("INT", {"default": 30, "min": 1, "max": 1000}),
            }
        }

    RETURN_TYPES = ("LIST", "INT")
    RETURN_NAMES = ("clips", "num_clips")
    FUNCTION = "split_video"
    CATEGORY = "云服务"

    def split_video(self, video_path, max_frames_per_clip):
        clips = []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频文件: {video_path}")
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            np_image = frame.astype(np.float32) / 255.0
            frames.append(torch.from_numpy(np_image))
            if len(frames) == max_frames_per_clip:
                clips.append(torch.stack(frames, dim=0))
                frames = []
        if frames:
            clips.append(torch.stack(frames, dim=0))
        cap.release()
        return (clips, len(clips))

class GetVideoClipByIndex:
    """
    传入 clips（张量序列列表）和索引，返回该片段合成的视频（mp4二进制）
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clips": ("LIST", {}),
                "index": ("INT", {"default": 0, "min": 0}),
                "fps": ("INT", {"default": 24, "min": 1, "max": 120}),
                "ext": (["mp4", "avi", "mov"], {"default": "mp4"}),
            }
        }

    RETURN_TYPES = ("BYTES",)
    RETURN_NAMES = ("video_bytes",)
    FUNCTION = "get_clip_video"
    CATEGORY = "云服务"

    def get_clip_video(self, clips, index, fps, ext):
        import tempfile
        import imageio_ffmpeg
        import os
        import io
        if not clips or index < 0 or index >= len(clips):
            raise IndexError("索引超出clips范围")
        clip = clips[index]
        arr = clip.cpu().numpy() if hasattr(clip, 'cpu') else clip
        img_list = [np.clip(255. * img, 0, 255).astype(np.uint8) for img in arr]
        height, width = img_list[0].shape[0], img_list[0].shape[1]
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
        import subprocess
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for im in img_list:
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        proc.wait()
        with open(tmp_path, "rb") as f:
            video_bytes = f.read()
        os.remove(tmp_path)
        return (video_bytes,)

NODE_CLASS_MAPPINGS = {
    "SplitVideoByFrames": SplitVideoByFrames,
    "GetVideoClipByIndex": GetVideoClipByIndex
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SplitVideoByFrames": "🎬 视频分段拆帧",
    "GetVideoClipByIndex": "🎞️ 获取片段视频"
}
