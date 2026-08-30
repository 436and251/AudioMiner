from pathlib import Path
from tts_builder.gui.system_check import HardwareInfo, recommendation_for


def test_nvidia_cuda_recommends_large_turbo():
    info = HardwareInfo(os_name='Windows', cpu_name='CPU', ram_gb=32, gpu_name='RTX 4060', cuda_available=True, ffmpeg_available=True, free_gb=100)
    rec = recommendation_for(info)
    assert rec.mode == 'cuda'
    assert rec.asr_model == 'large-v3-turbo'


def test_cpu_only_recommends_small():
    info = HardwareInfo(os_name='Windows', cpu_name='CPU', ram_gb=16, gpu_name=None, cuda_available=False, ffmpeg_available=True, free_gb=50)
    rec = recommendation_for(info)
    assert rec.mode == 'cpu'
    assert rec.asr_model == 'small'
