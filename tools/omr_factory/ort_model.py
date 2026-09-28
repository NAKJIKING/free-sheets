# -*- coding: utf-8 -*-
"""onnxruntime(CPU) 백엔드 래퍼 — CRNN 과 같은 호출면.

평가 스크립트(evaluate/eval_structure/evaluate_duet)가 --onnx 로 이걸 쓰면
파이토치 없이도 같은 코드 경로로 채점된다(앱 탑재 1단계 검증용).
"""
import numpy as np
import torch


class OrtCRNN:
    """net(x)->(B,T,C) 로짓 텐서, out_len, eval/to 무동작 — CRNN 호환."""

    down = 4

    def __init__(self, path, threads=0):
        import onnxruntime as ort
        so = ort.SessionOptions()
        if threads:
            so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(
            path, sess_options=so, providers=['CPUExecutionProvider'])
        self.inp = self.sess.get_inputs()[0].name

    def __call__(self, x):
        y = self.sess.run(None, {self.inp: np.ascontiguousarray(
            x.detach().cpu().numpy(), dtype=np.float32)})[0]
        return torch.from_numpy(y)

    forward = __call__

    def eval(self):
        return self

    def to(self, _dev):
        return self

    def out_len(self, in_w):
        return torch.clamp(in_w // self.down, min=1)
