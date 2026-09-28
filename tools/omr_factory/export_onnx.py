#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""앱 탑재 1단계 — 채택 CRNN 의 ONNX 내보내기·양자화·검증.

    python tools/omr_factory/export_onnx.py --model C:/Users/me/omr_model_3c4 \
        --out C:/Users/me/omr_export --data C:/Users/me/omr_lines

① FP32 ONNX 내보내기(가변 배치·가변 폭), 파이토치와 로짓/디코드 일치 확인
② INT8 동적 양자화본 생성 + 디코드 일치율
③ 크기·sha256 기록, CPU 한 줄 처리시간(평균/p50/최악) — torch/FP32/INT8
모델 파일은 저장소에 커밋하지 않는다(크기·해시만 일지에).
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
from model import CRNN, greedy_decode


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load_lines(data, n, seed=7):
    """시험 분할에서 폭이 고르게 퍼지도록 n 줄의 캐시 이미지를 뽑는다."""
    from PIL import Image
    rows = [json.loads(l) for l in
            open(os.path.join(data, 'index.jsonl'), encoding='utf-8')
            if '"test"' in l]
    rows.sort(key=lambda r: r['w'])
    step = max(1, len(rows) // n)
    out = []
    for r in rows[::step][:n]:
        with Image.open(os.path.join(data, r['cache'])) as im:
            out.append(np.asarray(im.convert('L'), dtype=np.float32) / 255.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--data', required=True, help='지연·일치 측정용 코퍼스')
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--lat-n', type=int, default=200)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    st = torch.load(os.path.join(a.model, a.ckpt), map_location='cpu')
    net = CRNN(len(vocab))
    net.load_state_dict(st['net'])
    net.eval()
    print(f"체크포인트 에폭 {st.get('epoch')} 어휘 {len(vocab)}")

    # ① FP32 내보내기 — 배치·폭 동적
    fp32 = os.path.join(a.out, 'omr_crnn_fp32.onnx')
    dummy = torch.zeros(1, 1, 160, 640)
    torch.onnx.export(
        net, dummy, fp32, opset_version=17,
        input_names=['x'], output_names=['logits'],
        dynamic_axes={'x': {0: 'batch', 3: 'width'},
                      'logits': {0: 'batch', 1: 'frames'}},
        dynamo=False)
    import onnx
    onnx.checker.check_model(onnx.load(fp32))
    print('FP32 내보내기 OK:', fp32)

    from ort_model import OrtCRNN
    ort32 = OrtCRNN(fp32)

    # 일치 검증 — 로짓 최대차 + 그리디 디코드 동일 여부 (다양한 폭)
    imgs = load_lines(a.data, 24)
    def dec(nete, x):
        with torch.no_grad():
            lg = nete(x)
        return greedy_decode(lg, torch.tensor([x.shape[3] // 4]))[0]
    same32 = 0
    maxd = 0.0
    for im in imgs:
        x = torch.from_numpy(im)[None, None]
        with torch.no_grad():
            lt = net(x)
        lo = ort32(x)
        maxd = max(maxd, float((lt - lo).abs().max()))
        same32 += (dec(net, x) == dec(ort32, x))
    print(f'FP32 일치: 디코드 {same32}/{len(imgs)} / 로짓 최대차 {maxd:.2e}')

    # ② INT8 동적 양자화
    int8 = os.path.join(a.out, 'omr_crnn_int8.onnx')
    from onnxruntime.quantization import quantize_dynamic, QuantType
    quantize_dynamic(fp32, int8, weight_type=QuantType.QInt8)
    ort8 = OrtCRNN(int8)
    same8 = sum((dec(ort32, torch.from_numpy(im)[None, None])
                 == dec(ort8, torch.from_numpy(im)[None, None]))
                for im in imgs)
    print(f'INT8 디코드 일치(vs FP32): {same8}/{len(imgs)}')

    # ③ 크기·해시 + CPU 한 줄 지연 (B=1)
    rep = dict(ckpt_epoch=st.get('epoch'), vocab=len(vocab),
               logit_maxdiff=maxd, decode_same_fp32=f'{same32}/{len(imgs)}',
               decode_same_int8=f'{same8}/{len(imgs)}')
    for tag, p in (('fp32', fp32), ('int8', int8)):
        rep[tag] = dict(bytes=os.path.getsize(p),
                        mb=round(os.path.getsize(p) / 2**20, 2),
                        sha256=sha256(p))
        print(tag, rep[tag]['mb'], 'MB', rep[tag]['sha256'][:16])

    lat_imgs = load_lines(a.data, a.lat_n)
    def bench(fn, warm=3):
        ts = []
        for i, im in enumerate(lat_imgs):
            x = torch.from_numpy(im)[None, None]
            t0 = time.perf_counter()
            with torch.no_grad():
                fn(x)
            dt = (time.perf_counter() - t0) * 1000
            if i >= warm:
                ts.append(dt)
        ts.sort()
        return dict(mean_ms=round(sum(ts) / len(ts), 1),
                    p50_ms=round(ts[len(ts) // 2], 1),
                    max_ms=round(ts[-1], 1))
    rep['lat_torch_cpu'] = bench(net)
    rep['lat_fp32'] = bench(ort32)
    rep['lat_int8'] = bench(ort8)
    for k in ('lat_torch_cpu', 'lat_fp32', 'lat_int8'):
        print(k, rep[k])
    json.dump(rep, open(os.path.join(a.out, 'export_report.json'), 'w'),
              indent=1)
    print('보고서 →', os.path.join(a.out, 'export_report.json'))


if __name__ == '__main__':
    main()
